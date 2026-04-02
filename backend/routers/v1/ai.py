"""AI model routes — workspace-scoped model configuration."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from middleware.workspace import WorkspaceContext, get_workspace_context, require_admin
from schemas.ai import AIModelConfig
from schemas.common import SuccessResponse
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_PROVIDERS = {"ollama", "anthropic", "openai", "kimi", "custom"}


@router.get("/workspaces/{workspace_id}/ai/models")
async def list_ai_models(ws: WorkspaceContext = Depends(get_workspace_context)):
    try:
        db = get_db()
        result = (
            db.table("ai_models")
            .select("*")
            .eq("workspace_id", ws.workspace_id)
            .order("name")
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error("Failed to list AI models for workspace %s: %s", ws.workspace_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch AI models")


@router.post("/workspaces/{workspace_id}/ai/models", status_code=201)
async def add_ai_model(data: AIModelConfig, ws: WorkspaceContext = Depends(require_admin)):
    if data.provider not in ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid provider '{data.provider}'. Allowed: {sorted(ALLOWED_PROVIDERS)}",
        )
    try:
        db = get_db()
        payload = data.model_dump()
        payload["workspace_id"] = ws.workspace_id
        result = db.table("ai_models").insert(payload).execute()
        return result.data[0]
    except Exception as e:
        logger.error("Failed to add AI model for workspace %s: %s", ws.workspace_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save AI model")


@router.put("/workspaces/{workspace_id}/ai/models/{model_id}/toggle")
async def toggle_ai_model(model_id: str, ws: WorkspaceContext = Depends(require_admin)):
    db = get_db()
    current = (
        db.table("ai_models")
        .select("is_active")
        .eq("id", model_id)
        .eq("workspace_id", ws.workspace_id)
        .limit(1)
        .execute()
    )
    if not current.data:
        return {"error": "Model not found"}
    new_state = not current.data[0]["is_active"]
    db.table("ai_models").update({"is_active": new_state}).eq("id", model_id).execute()
    return {"is_active": new_state}


@router.delete("/workspaces/{workspace_id}/ai/models/{model_id}")
async def delete_ai_model(model_id: str, ws: WorkspaceContext = Depends(require_admin)) -> SuccessResponse:
    db = get_db()
    db.table("ai_models").delete().eq("id", model_id).eq("workspace_id", ws.workspace_id).execute()
    return SuccessResponse()
