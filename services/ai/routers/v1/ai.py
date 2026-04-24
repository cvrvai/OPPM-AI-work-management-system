"""AI model routes — workspace-scoped model configuration."""

import logging
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context, require_admin
from schemas.ai import AIModelConfig
from shared.schemas.common import SuccessResponse
from shared.database import get_session
from shared.models.ai_model import AIModel

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_PROVIDERS = {"ollama", "anthropic", "openai", "kimi", "deepseek", "custom"}


@router.get("/workspaces/{workspace_id}/ai/models")
async def list_ai_models(
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.execute(
            select(AIModel)
            .where(AIModel.workspace_id == ws.workspace_id)
            .order_by(AIModel.name)
        )
        models = result.scalars().all()
        return [
            {
                "id": str(m.id), "workspace_id": str(m.workspace_id),
                "name": m.name, "provider": m.provider, "model_id": m.model_id,
                "endpoint_url": m.endpoint_url, "is_active": m.is_active,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in models
        ]
    except Exception as e:
        logger.error("Failed to list AI models for workspace %s: %s", ws.workspace_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch AI models")


@router.post("/workspaces/{workspace_id}/ai/models", status_code=201)
async def add_ai_model(
    data: AIModelConfig,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    if data.provider not in ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid provider '{data.provider}'. Allowed: {sorted(ALLOWED_PROVIDERS)}",
        )
    try:
        model = AIModel(
            workspace_id=ws.workspace_id,
            **data.model_dump(),
        )
        session.add(model)
        await session.flush()
        return {
            "id": str(model.id), "workspace_id": str(model.workspace_id),
            "name": model.name, "provider": model.provider, "model_id": model.model_id,
            "endpoint_url": model.endpoint_url, "is_active": model.is_active,
            "created_at": model.created_at.isoformat() if model.created_at else None,
        }
    except Exception as e:
        logger.error("Failed to add AI model for workspace %s: %s", ws.workspace_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save AI model")


@router.put("/workspaces/{workspace_id}/ai/models/{model_id}/toggle")
async def toggle_ai_model(
    model_id: str,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(AIModel)
        .where(AIModel.id == model_id, AIModel.workspace_id == ws.workspace_id)
        .limit(1)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="AI model not found")
    model.is_active = not model.is_active
    await session.flush()
    return {"is_active": model.is_active}


@router.delete("/workspaces/{workspace_id}/ai/models/{model_id}")
async def delete_ai_model(
    model_id: str,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    result = await session.execute(
        select(AIModel)
        .where(AIModel.id == model_id, AIModel.workspace_id == ws.workspace_id)
        .limit(1)
    )
    model = result.scalar_one_or_none()
    if model:
        await session.delete(model)
        await session.flush()
    return SuccessResponse()


# ── OCR: extract OPPM structure from an image ──────────────────────────────

_OPPM_EXTRACT_PROMPT = """\
You are an OPPM (One Page Project Manager) data extraction assistant.
Analyse the image of an OPPM sheet and return ONLY a valid JSON object — no
markdown, no extra text — matching this exact structure:

{
  "project_title": "<string or null>",
  "project_objective": "<string or null>",
  "deliverable_output": "<string or null>",
  "sub_objectives": [
    {"position": 1, "label": "<string>"},
    ...up to 6
  ],
  "objectives": [
    {
      "title": "<string>",
      "tasks": [
        {
          "name": "<string>",
          "due_date": "<YYYY-MM-DD or null>",
          "sub_obj_positions": [1, 3]
        }
      ]
    }
  ],
  "deliverables": ["<string>"],
  "forecasts": ["<string>"],
  "risks": [
    {"description": "<string>", "rag": "green|amber|red"}
  ]
}

Rules:
- "sub_obj_positions" should list which position numbers (1-6) the task
  links to, based on the checkmarks visible in the image.
- If a field is not visible, use null or an empty array as appropriate.
- Dates must be ISO 8601 (YYYY-MM-DD). If only a month/year is shown,
  estimate as the last day of that month.
- RAG colours: green = on-track, amber = at-risk, red = critical.
"""


@router.post("/workspaces/{workspace_id}/ai/oppm-extract")
async def extract_oppm_from_image(
    workspace_id: str,
    file: UploadFile = File(..., description="Image file: PNG, JPEG, or WEBP"),
    model_id: str = Query(default="llava", description="Ollama vision model name"),
    ws: WorkspaceContext = Depends(get_workspace_context),
):
    """Use an Ollama vision model to extract OPPM data from an uploaded image.

    Returns structured JSON ready to be reviewed and then sent to
    POST .../oppm/import-json on the core service.
    Does NOT save anything to the database.
    """
    allowed = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    ct = (file.content_type or "").lower()
    if ct not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ct}'. Upload PNG, JPEG, or WEBP.",
        )

    image_bytes = await file.read()
    if len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image must be under 20 MB")

    from infrastructure.llm.ollama import OllamaAdapter
    from infrastructure.llm.base import ProviderUnavailableError

    try:
        adapter = OllamaAdapter()
        result = await adapter.call_vision_json(model_id, _OPPM_EXTRACT_PROMPT, image_bytes)
    except ProviderUnavailableError as e:
        logger.warning("Ollama unavailable for OPPM extract: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Ollama is not reachable. Make sure the '{model_id}' model is running.",
        )

    if result is None:
        raise HTTPException(
            status_code=422,
            detail="The vision model did not return parseable JSON. Try a different model or a clearer image.",
        )

    logger.info(
        "OPPM extract completed for workspace %s using model %s: %d objectives",
        workspace_id, model_id, len(result.get("objectives", [])),
    )
    return result
