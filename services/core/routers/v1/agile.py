"""Agile routes — epics, user stories, sprints, retrospectives (workspace-scoped)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import WorkspaceContext, get_workspace_context, require_write
from shared.database import get_session
from shared.schemas.common import SuccessResponse
from schemas.agile import (
    EpicCreate, EpicUpdate,
    UserStoryCreate, UserStoryUpdate, UserStoryReorder,
    SprintCreate, SprintUpdate,
    RetrospectiveCreate, RetrospectiveUpdate,
)
from services.agile_service import (
    list_epics, create_epic, update_epic, delete_epic,
    list_user_stories, create_user_story, update_user_story, delete_user_story, reorder_user_stories,
    list_sprints, create_sprint, update_sprint, delete_sprint, start_sprint, complete_sprint, get_burndown,
    get_retrospective, create_retrospective, update_retrospective,
)

router = APIRouter()


# ── Epics ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/epics")
async def list_epics_route(
    project_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_epics(session, project_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/epics", status_code=201)
async def create_epic_route(
    project_id: str,
    data: EpicCreate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await create_epic(session, ws.workspace_id, project_id, ws.user.id, data.model_dump(mode="json"))


@router.put("/workspaces/{workspace_id}/projects/{project_id}/epics/{epic_id}")
async def update_epic_route(
    project_id: str,
    epic_id: str,
    data: EpicUpdate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await update_epic(session, epic_id, ws.workspace_id, ws.user.id, data.model_dump(mode="json", exclude_none=True))


@router.delete("/workspaces/{workspace_id}/projects/{project_id}/epics/{epic_id}")
async def delete_epic_route(
    project_id: str,
    epic_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_epic(session, epic_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── User Stories ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/user-stories")
async def list_user_stories_route(
    project_id: str,
    sprint_id: str | None = Query(None),
    epic_id: str | None = Query(None),
    status: str | None = Query(None),
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_user_stories(session, project_id, sprint_id=sprint_id, epic_id=epic_id, status=status)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/user-stories", status_code=201)
async def create_user_story_route(
    project_id: str,
    data: UserStoryCreate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await create_user_story(session, ws.workspace_id, project_id, ws.user.id, ws.member_id, data.model_dump(mode="json"))


@router.put("/workspaces/{workspace_id}/projects/{project_id}/user-stories/{story_id}")
async def update_user_story_route(
    project_id: str,
    story_id: str,
    data: UserStoryUpdate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await update_user_story(session, story_id, ws.workspace_id, ws.user.id, data.model_dump(mode="json", exclude_none=True))


@router.delete("/workspaces/{workspace_id}/projects/{project_id}/user-stories/{story_id}")
async def delete_user_story_route(
    project_id: str,
    story_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_user_story(session, story_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


@router.put("/workspaces/{workspace_id}/projects/{project_id}/user-stories/reorder")
async def reorder_user_stories_route(
    project_id: str,
    data: UserStoryReorder,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await reorder_user_stories(session, data.story_ids)


# ── Sprints ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/sprints")
async def list_sprints_route(
    project_id: str,
    status: str | None = Query(None),
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_sprints(session, project_id, status=status)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/sprints", status_code=201)
async def create_sprint_route(
    project_id: str,
    data: SprintCreate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await create_sprint(session, ws.workspace_id, project_id, ws.user.id, data.model_dump(mode="json"))


@router.put("/workspaces/{workspace_id}/projects/{project_id}/sprints/{sprint_id}")
async def update_sprint_route(
    project_id: str,
    sprint_id: str,
    data: SprintUpdate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await update_sprint(session, sprint_id, ws.workspace_id, ws.user.id, data.model_dump(mode="json", exclude_none=True))


@router.delete("/workspaces/{workspace_id}/projects/{project_id}/sprints/{sprint_id}")
async def delete_sprint_route(
    project_id: str,
    sprint_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_sprint(session, sprint_id, ws.workspace_id, ws.user.id)
    return SuccessResponse()


@router.post("/workspaces/{workspace_id}/projects/{project_id}/sprints/{sprint_id}/start")
async def start_sprint_route(
    project_id: str,
    sprint_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await start_sprint(session, sprint_id, ws.workspace_id, ws.user.id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/sprints/{sprint_id}/complete")
async def complete_sprint_route(
    project_id: str,
    sprint_id: str,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await complete_sprint(session, sprint_id, ws.workspace_id, ws.user.id)


@router.get("/workspaces/{workspace_id}/projects/{project_id}/sprints/{sprint_id}/burndown")
async def get_burndown_route(
    project_id: str,
    sprint_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await get_burndown(session, sprint_id, ws.workspace_id)


# ── Retrospectives ──

@router.get("/workspaces/{workspace_id}/projects/{project_id}/sprints/{sprint_id}/retrospective")
async def get_retrospective_route(
    project_id: str,
    sprint_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await get_retrospective(session, sprint_id, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/projects/{project_id}/sprints/{sprint_id}/retrospective", status_code=201)
async def create_retrospective_route(
    project_id: str,
    sprint_id: str,
    data: RetrospectiveCreate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await create_retrospective(session, ws.workspace_id, project_id, sprint_id, ws.user.id, ws.member_id, data.model_dump(mode="json"))


@router.put("/workspaces/{workspace_id}/projects/{project_id}/sprints/{sprint_id}/retrospective")
async def update_retrospective_route(
    project_id: str,
    sprint_id: str,
    data: RetrospectiveUpdate,
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    return await update_retrospective(session, sprint_id, ws.workspace_id, ws.user.id, data.model_dump(mode="json", exclude_none=True))
