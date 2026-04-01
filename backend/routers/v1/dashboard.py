"""Dashboard routes — workspace-scoped stats."""

from fastapi import APIRouter, Depends
from middleware.workspace import WorkspaceContext, get_workspace_context
from services.dashboard_service import get_dashboard_stats

router = APIRouter()


@router.get("/workspaces/{workspace_id}/dashboard/stats")
async def dashboard_stats(ws: WorkspaceContext = Depends(get_workspace_context)):
    return get_dashboard_stats(ws.workspace_id)
