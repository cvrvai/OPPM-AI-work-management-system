"""AI model routes — workspace-scoped model configuration."""

from fastapi import APIRouter, Depends
from middleware.workspace import WorkspaceContext, get_workspace_context, require_admin
from schemas.ai import AIModelConfig
from schemas.common import SuccessResponse
from database import get_db

router = APIRouter()


@router.get("/workspaces/{workspace_id}/ai/models")
async def list_ai_models(ws: WorkspaceContext = Depends(get_workspace_context)):
    db = get_db()
    result = (
        db.table("ai_models")
        .select("*")
        .eq("workspace_id", ws.workspace_id)
        .order("name")
        .execute()
    )
    return result.data


@router.post("/workspaces/{workspace_id}/ai/models", status_code=201)
async def add_ai_model(data: AIModelConfig, ws: WorkspaceContext = Depends(require_admin)):
    db = get_db()
    payload = data.model_dump()
    payload["workspace_id"] = ws.workspace_id
    result = db.table("ai_models").insert(payload).execute()
    return result.data[0]


@router.put("/workspaces/{workspace_id}/ai/models/{model_id}/toggle")
async def toggle_ai_model(model_id: str, ws: WorkspaceContext = Depends(require_admin)):
    db = get_db()
    current = (
        db.table("ai_models")
        .select("is_active")
        .eq("id", model_id)
        .eq("workspace_id", ws.workspace_id)
        .maybe_single()
        .execute()
    )
    if not current.data:
        return {"error": "Model not found"}
    new_state = not current.data["is_active"]
    db.table("ai_models").update({"is_active": new_state}).eq("id", model_id).execute()
    return {"is_active": new_state}


@router.delete("/workspaces/{workspace_id}/ai/models/{model_id}")
async def delete_ai_model(model_id: str, ws: WorkspaceContext = Depends(require_admin)) -> SuccessResponse:
    db = get_db()
    db.table("ai_models").delete().eq("id", model_id).eq("workspace_id", ws.workspace_id).execute()
    return SuccessResponse()
