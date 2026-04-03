"""OPPM routes — objectives, timeline, costs."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context, require_write
from shared.database import get_session
from schemas.oppm import OPPMObjectiveCreate, OPPMObjectiveUpdate, TimelineEntryUpsert, CostCreate, CostUpdate
from shared.schemas.common import SuccessResponse
from services.oppm_service import (
    get_objectives_with_tasks,
    create_objective,
    update_objective,
    delete_objective,
    get_timeline,
    upsert_timeline_entry,
    get_costs,
    create_cost,
    update_cost,
    delete_cost,
)

router = APIRouter()


# ── Objectives ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/objectives")
async def list_objectives_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_objectives_with_tasks(session, project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/objectives", status_code=201)
async def create_objective_route(project_id: str, data: OPPMObjectiveCreate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await create_objective(session, project_id, data.model_dump(), ws.workspace_id, ws.user.id)


@router.put("/workspaces/{workspace_id}/oppm/objectives/{objective_id}")
async def update_objective_route(objective_id: str, data: OPPMObjectiveUpdate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await update_objective(session, objective_id, data.model_dump(exclude_none=True), ws.workspace_id, ws.user.id)


@router.delete("/workspaces/{workspace_id}/oppm/objectives/{objective_id}")
async def delete_objective_route(objective_id: str, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await delete_objective(session, objective_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Timeline ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/timeline")
async def get_timeline_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_timeline(session, project_id, ws.workspace_id)


@router.put("/workspaces/{workspace_id}/projects/{project_id}/oppm/timeline")
async def upsert_timeline_route(project_id: str, data: TimelineEntryUpsert, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    payload = data.model_dump(exclude_none=True)
    payload["project_id"] = project_id
    return await upsert_timeline_entry(session, payload, ws.workspace_id, ws.user.id)


# ── Costs ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/costs")
async def list_costs_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_costs(session, project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/costs", status_code=201)
async def create_cost_route(project_id: str, data: CostCreate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await create_cost(session, project_id, data.model_dump(), ws.workspace_id, ws.user.id)


@router.put("/workspaces/{workspace_id}/oppm/costs/{cost_id}")
async def update_cost_route(cost_id: str, data: CostUpdate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await update_cost(session, cost_id, data.model_dump(exclude_none=True), ws.workspace_id, ws.user.id)


@router.delete("/workspaces/{workspace_id}/oppm/costs/{cost_id}")
async def delete_cost_route(cost_id: str, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await delete_cost(session, cost_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()
