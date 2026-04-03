"""AI model routes — workspace-scoped model configuration."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context, require_admin
from schemas.ai import AIModelConfig
from shared.schemas.common import SuccessResponse
from shared.database import get_session
from shared.models.ai_model import AIModel

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_PROVIDERS = {"ollama", "anthropic", "openai", "kimi", "custom"}


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
