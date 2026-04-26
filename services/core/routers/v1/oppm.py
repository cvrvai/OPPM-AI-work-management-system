"""OPPM routes — objectives, timeline, costs, sub-objectives, task-owners, deliverables, forecasts, risks, export."""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context, require_write
from shared.database import get_session
from schemas.oppm import (
    OPPMObjectiveCreate, OPPMObjectiveUpdate, TimelineEntryUpsert,
    CostCreate, CostUpdate,
    SubObjectiveCreate, SubObjectiveUpdate, TaskSubObjectiveSet,
    TaskOwnerSet,
    DeliverableCreate, DeliverableUpdate,
    ForecastCreate, ForecastUpdate,
    RiskCreate, RiskUpdate,
    OPPMHeaderUpsert,
    OPPMTaskItemsReplace,
)
from schemas.google_sheets import GoogleSheetLinkResponse, GoogleSheetLinkUpsert, GoogleSheetPushRequest, GoogleSheetPushResponse
from shared.schemas.common import SuccessResponse
from services.oppm_service import (
    get_oppm_data,
    get_objectives_with_tasks,
    create_objective,
    update_objective,
    delete_objective,
    get_sub_objectives,
    create_sub_objective,
    update_sub_objective,
    delete_sub_objective,
    set_task_sub_objectives,
    set_task_owner,
    remove_task_owner,
    get_timeline,
    upsert_timeline_entry,
    get_costs,
    create_cost,
    update_cost,
    delete_cost,
    get_deliverables,
    create_deliverable,
    update_deliverable,
    delete_deliverable,
    get_forecasts,
    create_forecast,
    update_forecast,
    delete_forecast,
    get_risks,
    create_risk,
    update_risk,
    delete_risk,
    get_oppm_header,
    upsert_oppm_header,
    get_oppm_task_items,
    replace_oppm_task_items,
)
from services.export_service import export_oppm_xlsx, import_oppm_xlsx, import_oppm_json, parse_oppm_xlsx_to_preview
from services.google_sheets_service import (
    get_google_sheet_link,
    upsert_google_sheet_link,
    delete_google_sheet_link,
    push_google_sheet_fill,
    download_linked_google_sheet_xlsx,
)
from repositories.oppm_repo import OPPMTemplateRepository

router = APIRouter()


# ── Combined OPPM Data ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm")
async def get_oppm_data_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_oppm_data(session, project_id, ws.workspace_id)


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


# ── Sub-Objectives ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/sub-objectives")
async def list_sub_objectives_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_sub_objectives(session, project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/sub-objectives", status_code=201)
async def create_sub_objective_route(project_id: str, data: SubObjectiveCreate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await create_sub_objective(session, project_id, data.model_dump(), ws.workspace_id, ws.user.id)


@router.put("/workspaces/{workspace_id}/oppm/sub-objectives/{sub_obj_id}")
async def update_sub_objective_route(sub_obj_id: str, data: SubObjectiveUpdate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await update_sub_objective(session, sub_obj_id, data.model_dump(exclude_none=True), ws.workspace_id)


@router.delete("/workspaces/{workspace_id}/oppm/sub-objectives/{sub_obj_id}")
async def delete_sub_objective_route(sub_obj_id: str, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await delete_sub_objective(session, sub_obj_id, ws.workspace_id)
    return SuccessResponse()


@router.put("/workspaces/{workspace_id}/projects/{project_id}/oppm/tasks/{task_id}/sub-objectives")
async def set_task_sub_objectives_route(project_id: str, task_id: str, data: TaskSubObjectiveSet, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await set_task_sub_objectives(session, project_id, task_id, data.sub_objective_ids, ws.workspace_id)


# ── Task Owners (A/B/C) ──

@router.put("/workspaces/{workspace_id}/projects/{project_id}/oppm/tasks/{task_id}/owners")
async def set_task_owner_route(project_id: str, task_id: str, data: TaskOwnerSet, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await set_task_owner(session, project_id, task_id, data.member_id, data.priority, ws.workspace_id)


@router.delete("/workspaces/{workspace_id}/projects/{project_id}/oppm/tasks/{task_id}/owners/{member_id}")
async def remove_task_owner_route(project_id: str, task_id: str, member_id: str, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    await remove_task_owner(session, project_id, task_id, member_id, ws.workspace_id)
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


# ── Deliverables ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/deliverables")
async def list_deliverables_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_deliverables(session, project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/deliverables", status_code=201)
async def create_deliverable_route(project_id: str, data: DeliverableCreate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await create_deliverable(session, project_id, data.model_dump(), ws.workspace_id)


@router.put("/workspaces/{workspace_id}/oppm/deliverables/{item_id}")
async def update_deliverable_route(item_id: str, data: DeliverableUpdate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await update_deliverable(session, item_id, data.model_dump(exclude_none=True), ws.workspace_id)


@router.delete("/workspaces/{workspace_id}/oppm/deliverables/{item_id}")
async def delete_deliverable_route(item_id: str, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await delete_deliverable(session, item_id, ws.workspace_id)
    return SuccessResponse()


# ── Forecasts ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/forecasts")
async def list_forecasts_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_forecasts(session, project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/forecasts", status_code=201)
async def create_forecast_route(project_id: str, data: ForecastCreate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await create_forecast(session, project_id, data.model_dump(), ws.workspace_id)


@router.put("/workspaces/{workspace_id}/oppm/forecasts/{item_id}")
async def update_forecast_route(item_id: str, data: ForecastUpdate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await update_forecast(session, item_id, data.model_dump(exclude_none=True), ws.workspace_id)


@router.delete("/workspaces/{workspace_id}/oppm/forecasts/{item_id}")
async def delete_forecast_route(item_id: str, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await delete_forecast(session, item_id, ws.workspace_id)
    return SuccessResponse()


# ── Risks ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/risks")
async def list_risks_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_risks(session, project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/risks", status_code=201)
async def create_risk_route(project_id: str, data: RiskCreate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await create_risk(session, project_id, data.model_dump(), ws.workspace_id)


@router.put("/workspaces/{workspace_id}/oppm/risks/{item_id}")
async def update_risk_route(item_id: str, data: RiskUpdate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await update_risk(session, item_id, data.model_dump(exclude_none=True), ws.workspace_id)


@router.delete("/workspaces/{workspace_id}/oppm/risks/{item_id}")
async def delete_risk_route(item_id: str, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await delete_risk(session, item_id, ws.workspace_id)
    return SuccessResponse()


# ── Export ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/export")
async def export_oppm_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    xlsx_bytes = await export_oppm_xlsx(session, project_id, ws.workspace_id)
    filename = f"oppm-export-{project_id[:8]}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Import Template ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/template")
async def get_oppm_template_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    from exports.oppm_exporter import build_oppm_template
    from repositories.project_repo import ProjectRepository
    prj = await ProjectRepository(session).find_by_id(project_id)
    xlsx_bytes = build_oppm_template(prj.title if prj else "")
    filename = f"oppm-template-{project_id[:8]}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Import XLSX ──

@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/import")
async def import_oppm_route(
    project_id: str,
    file: UploadFile = File(...),
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    xlsx_bytes = await file.read()
    return await import_oppm_xlsx(session, project_id, ws.workspace_id, xlsx_bytes)


# ── Preview XLSX (parse without saving) ──

@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/preview-xlsx")
async def preview_oppm_xlsx_route(
    project_id: str,
    file: UploadFile = File(...),
    ws: WorkspaceContext = Depends(get_workspace_context),
):
    """Parse the uploaded XLSX and return structured preview JSON — no DB writes."""
    xlsx_bytes = await file.read()
    return parse_oppm_xlsx_to_preview(xlsx_bytes)


# ── Import JSON (from AI OCR extractor) ──

@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/import-json")
async def import_oppm_json_route(
    project_id: str,
    data: dict,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    """Save structured OPPM JSON (from AI OCR preview) to the database."""
    return await import_oppm_json(session, project_id, ws.workspace_id, data)


# ── Spreadsheet Template (FortuneSheet) ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/spreadsheet")
async def get_spreadsheet_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Return the FortuneSheet JSON data for this project, or 404 if none."""
    from fastapi import HTTPException
    repo = OPPMTemplateRepository(session)
    tpl = await repo.find_by_project(project_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="No spreadsheet template for this project")
    return {"sheet_data": tpl.sheet_data, "file_name": tpl.file_name}


@router.put("/workspaces/{workspace_id}/projects/{project_id}/oppm/spreadsheet")
async def upsert_spreadsheet_route(
    project_id: str,
    data: dict,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    """Upsert FortuneSheet JSON data for this project."""
    repo = OPPMTemplateRepository(session)
    sheet_data = data.get("sheet_data", [])
    file_name = data.get("file_name")
    tpl = await repo.upsert(project_id, ws.workspace_id, sheet_data, file_name)
    return {"id": str(tpl.id), "file_name": tpl.file_name, "updated": True}


@router.delete("/workspaces/{workspace_id}/projects/{project_id}/oppm/spreadsheet")
async def delete_spreadsheet_route(
    project_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    """Delete the spreadsheet template, reverting to system OPPM view."""
    repo = OPPMTemplateRepository(session)
    await repo.delete_by_project(project_id)
    return {"deleted": True}


# ── Google Sheets MVP ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet", response_model=GoogleSheetLinkResponse)
async def get_google_sheet_link_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await get_google_sheet_link(session, project_id, ws.workspace_id)


@router.put("/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet", response_model=GoogleSheetLinkResponse)
async def upsert_google_sheet_link_route(
    project_id: str,
    data: GoogleSheetLinkUpsert,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    spreadsheet_input = data.spreadsheet_url or data.spreadsheet_id or ""
    return await upsert_google_sheet_link(session, project_id, ws.workspace_id, ws.user.id, spreadsheet_input)


@router.delete("/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet")
async def delete_google_sheet_link_route(
    project_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_google_sheet_link(session, project_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


@router.post("/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet/push", response_model=GoogleSheetPushResponse)
async def push_google_sheet_fill_route(
    project_id: str,
    data: GoogleSheetPushRequest,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await push_google_sheet_fill(
        session,
        project_id,
        ws.workspace_id,
        ws.user.id,
        data.fills,
        data.tasks,
        data.members,
    )


@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/google-sheet/xlsx")
async def download_linked_google_sheet_xlsx_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    xlsx_bytes, file_name = await download_linked_google_sheet_xlsx(session, project_id, ws.workspace_id)
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


# ── OPPM Header ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/header")
async def get_oppm_header_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Return the OPPM form header fields for a project."""
    return await get_oppm_header(session, project_id, ws.workspace_id)


@router.put("/workspaces/{workspace_id}/projects/{project_id}/oppm/header")
async def upsert_oppm_header_route(
    project_id: str,
    data: OPPMHeaderUpsert,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    """Create or update the OPPM header fields for a project."""
    return await upsert_oppm_header(session, project_id, data.model_dump(exclude_none=True), ws.workspace_id)


# ── OPPM Task Items ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/oppm/task-items")
async def list_oppm_task_items_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Return the OPPM task items tree (major tasks with children) for a project."""
    return await get_oppm_task_items(session, project_id, ws.workspace_id)


@router.put("/workspaces/{workspace_id}/projects/{project_id}/oppm/task-items")
async def replace_oppm_task_items_route(
    project_id: str,
    data: OPPMTaskItemsReplace,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    """Full replace of OPPM task items for a project (delete-all then re-insert)."""
    items = [i.model_dump() for i in data.items]
    return await replace_oppm_task_items(session, project_id, items, ws.workspace_id)
