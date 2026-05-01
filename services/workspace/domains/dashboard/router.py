"""Dashboard routes — workspace-scoped stats."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context
from shared.database import get_session
from domains.dashboard.service import get_dashboard_stats

router = APIRouter()


@router.get("/workspaces/{workspace_id}/dashboard/stats")
async def dashboard_stats(ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_dashboard_stats(session, ws.workspace_id)
