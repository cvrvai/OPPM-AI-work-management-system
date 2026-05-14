"""Project routes — workspace-scoped CRUD + project members."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context, require_write
from shared.database import get_session
from domains.project.schemas import ProjectCreate, ProjectUpdate, ProjectMemberAdd
from shared.schemas.common import SuccessResponse
from domains.project.service import (
    list_projects,
    get_project,
    create_project,
    update_project,
    delete_project,
    get_project_members,
    add_project_member,
    remove_project_member,
)

router = APIRouter()


@router.get("/workspaces/{workspace_id}/projects")
async def list_projects_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    offset = (page - 1) * page_size
    return await list_projects(session, ws.workspace_id, status=status, limit=page_size, offset=offset)


@router.get("/workspaces/{workspace_id}/projects/{project_id}")
async def get_project_route(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_project(session, project_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects", status_code=201)
async def create_project_route(data: ProjectCreate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await create_project(session, ws.workspace_id, ws.user.id, data.model_dump(mode='json'), ws.member_id)


@router.put("/workspaces/{workspace_id}/projects/{project_id}")
async def update_project_route(project_id: str, data: ProjectUpdate, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await update_project(session, project_id, ws.workspace_id, ws.user.id, data.model_dump(mode='json', exclude_none=True))


@router.delete("/workspaces/{workspace_id}/projects/{project_id}")
async def delete_project_route(project_id: str, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await delete_project(session, project_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Project Members ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/members")
async def list_project_members(project_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_project_members(session, project_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/members", status_code=201)
async def add_project_member_route(project_id: str, data: ProjectMemberAdd, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    return await add_project_member(session, project_id, ws.workspace_id, data.user_id, data.role)


@router.delete("/workspaces/{workspace_id}/projects/{project_id}/members/{member_id}")
async def remove_project_member_route(project_id: str, member_id: str, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await remove_project_member(session, project_id, member_id)
    return SuccessResponse()
