"""Task routes — workspace-scoped CRUD + task reports."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import WorkspaceContext, get_workspace_context, require_write
from shared.database import get_session
from schemas.task import TaskCreate, TaskUpdate, TaskReportCreate, TaskReportApprove
from shared.schemas.common import SuccessResponse
from services.task_service import (
    list_tasks,
    get_task,
    create_task,
    update_task,
    delete_task,
    list_task_reports,
    create_task_report,
    approve_task_report,
    delete_task_report,
)

router = APIRouter()


@router.get("/workspaces/{workspace_id}/tasks")
async def list_tasks_route(
    project_id: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * page_size
    return await list_tasks(session, workspace_id=ws.workspace_id, project_id=project_id, status=status, limit=page_size, offset=offset)


@router.get("/workspaces/{workspace_id}/tasks/{task_id}")
async def get_task_route(
    task_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await get_task(session, task_id, workspace_id=ws.workspace_id)


@router.post("/workspaces/{workspace_id}/tasks", status_code=201)
async def create_task_route(
    data: TaskCreate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await create_task(session, data=data.model_dump(), workspace_id=ws.workspace_id, user_id=ws.user.id, member_id=ws.member_id)


@router.put("/workspaces/{workspace_id}/tasks/{task_id}")
async def update_task_route(
    task_id: str,
    data: TaskUpdate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await update_task(session, task_id=task_id, data=data.model_dump(exclude_none=True), workspace_id=ws.workspace_id, user_id=ws.user.id)


@router.delete("/workspaces/{workspace_id}/tasks/{task_id}")
async def delete_task_route(
    task_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_task(session, task_id=task_id, workspace_id=ws.workspace_id, user_id=ws.user.id)
    return SuccessResponse()


@router.get("/workspaces/{workspace_id}/tasks/{task_id}/reports")
async def list_task_reports_route(
    task_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_task_reports(session, task_id)


@router.post("/workspaces/{workspace_id}/tasks/{task_id}/reports", status_code=201)
async def create_task_report_route(
    task_id: str,
    data: TaskReportCreate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await create_task_report(session, task_id, ws.user.id, ws.member_id, data.model_dump())


@router.post("/workspaces/{workspace_id}/tasks/{task_id}/reports/{report_id}/approve")
async def approve_task_report_route(
    task_id: str,
    report_id: str,
    data: TaskReportApprove,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await approve_task_report(session, report_id, ws.user.id, data.model_dump())


@router.delete("/workspaces/{workspace_id}/tasks/{task_id}/reports/{report_id}")
async def delete_task_report_route(
    task_id: str,
    report_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_task_report(session, report_id, ws.user.id)
    return SuccessResponse()
