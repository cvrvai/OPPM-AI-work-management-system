"""OPPM routes — objectives, timeline, costs."""

from fastapi import APIRouter, Depends
from middleware.workspace import WorkspaceContext, get_workspace_context, require_write
from schemas.oppm import OPPMObjectiveCreate, OPPMObjectiveUpdate, TimelineEntryUpsert, CostCreate, CostUpdate
from schemas.common import SuccessResponse
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
async def list_objectives_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context)):
    return get_objectives_with_tasks(project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/objectives", status_code=201)
async def create_objective_route(project_id: str, data: OPPMObjectiveCreate, ws: WorkspaceContext = Depends(require_write)):
    return create_objective(project_id, data.model_dump(), ws.workspace_id, ws.user.id)


@router.put("/workspaces/{workspace_id}/oppm/objectives/{objective_id}")
async def update_objective_route(objective_id: str, data: OPPMObjectiveUpdate, ws: WorkspaceContext = Depends(require_write)):
    return update_objective(objective_id, data.model_dump(exclude_none=True), ws.workspace_id, ws.user.id)


@router.delete("/workspaces/{workspace_id}/oppm/objectives/{objective_id}")
async def delete_objective_route(objective_id: str, ws: WorkspaceContext = Depends(require_write)) -> SuccessResponse:
    delete_objective(objective_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Timeline ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/timeline")
async def get_timeline_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context)):
    return get_timeline(project_id, ws.workspace_id)


@router.put("/workspaces/{workspace_id}/projects/{project_id}/oppm/timeline")
async def upsert_timeline_route(project_id: str, data: TimelineEntryUpsert, ws: WorkspaceContext = Depends(require_write)):
    payload = data.model_dump()
    payload["project_id"] = project_id
    return upsert_timeline_entry(payload, ws.workspace_id, ws.user.id)


# ── Costs ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/costs")
async def list_costs_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context)):
    return get_costs(project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/costs", status_code=201)
async def create_cost_route(project_id: str, data: CostCreate, ws: WorkspaceContext = Depends(require_write)):
    return create_cost(project_id, data.model_dump(), ws.workspace_id, ws.user.id)


@router.put("/workspaces/{workspace_id}/oppm/costs/{cost_id}")
async def update_cost_route(cost_id: str, data: CostUpdate, ws: WorkspaceContext = Depends(require_write)):
    return update_cost(cost_id, data.model_dump(exclude_none=True), ws.workspace_id, ws.user.id)


@router.delete("/workspaces/{workspace_id}/oppm/costs/{cost_id}")
async def delete_cost_route(cost_id: str, ws: WorkspaceContext = Depends(require_write)) -> SuccessResponse:
    delete_cost(cost_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()
