"""
Workspace v1 routes — CRUD, members, invites, skills.
Migrated from services/core/routers/v1/workspaces.py
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import (
    CurrentUser,
    get_current_user,
    WorkspaceContext,
    get_workspace_context,
    require_admin,
    require_owner,
)
from shared.database import get_session
from schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    MemberUpdate,
    InviteCreate,
    DisplayNameUpdate,
    MemberSkillCreate,
)
from shared.schemas.common import SuccessResponse
from services.workspace_service import (
    create_workspace,
    get_workspace,
    get_user_workspaces,
    update_workspace,
    delete_workspace,
    get_workspace_members,
    update_member_role,
    remove_member,
    update_my_display_name,
    create_invite,
    accept_invite,
    get_pending_invites,
    revoke_invite,
    lookup_user_by_email,
    get_invite_preview,
    resend_invite,
    list_member_skills,
    add_member_skill,
    delete_member_skill,
    list_my_invites,
    decline_invite,
)

router = APIRouter()


# ── Workspace CRUD ────────────────────────────────────────────────────────────

@router.get("/workspaces")
async def list_workspaces_route(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await get_user_workspaces(session, user.id)


@router.post("/workspaces", status_code=201)
async def create_workspace_route(
    data: WorkspaceCreate,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await create_workspace(session, user.id, data.name, data.slug, data.description)


@router.get("/workspaces/{workspace_id}")
async def get_workspace_route(
    workspace_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await get_workspace(session, workspace_id, user.id)


@router.put("/workspaces/{workspace_id}")
async def update_workspace_route(
    data: WorkspaceUpdate,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await update_workspace(session, ws.workspace_id, ws.user.id, data.model_dump(exclude_none=True))


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace_route(
    ws: WorkspaceContext = Depends(require_owner),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_workspace(session, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Members ───────────────────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/members")
async def list_members_route(
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await get_workspace_members(session, ws.workspace_id)


@router.put("/workspaces/{workspace_id}/members/{member_id}")
async def update_member_route(
    member_id: str,
    data: MemberUpdate,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await update_member_role(session, ws.workspace_id, member_id, data.role.value, ws.user.id)


@router.delete("/workspaces/{workspace_id}/members/{member_id}")
async def remove_member_route(
    member_id: str,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await remove_member(session, ws.workspace_id, member_id, ws.user.id)
    return SuccessResponse()


@router.patch("/workspaces/{workspace_id}/members/me/display-name")
async def update_display_name_route(
    data: DisplayNameUpdate,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await update_my_display_name(session, ws.workspace_id, ws.user.id, data.display_name)


# ── Invites ───────────────────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/invites")
async def list_invites_route(
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await get_pending_invites(session, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/invites", status_code=201)
async def create_invite_route(
    data: InviteCreate,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await create_invite(session, ws.workspace_id, data.email, data.role, ws.user.id)


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}")
async def revoke_invite_route(
    invite_id: str,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await revoke_invite(session, ws.workspace_id, invite_id)
    return SuccessResponse()


@router.post("/workspaces/{workspace_id}/invites/{invite_id}/resend")
async def resend_invite_route(
    invite_id: str,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await resend_invite(session, ws.workspace_id, invite_id)


@router.get("/invite/{token}/preview")
async def preview_invite_route(token: str, session: AsyncSession = Depends(get_session)):
    return await get_invite_preview(session, token)


@router.post("/invite/{token}/accept")
async def accept_invite_route(
    token: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await accept_invite(session, token, user.id)


# ── User invitations (cross-workspace) ───────────────────────────────────────

@router.get("/invitations")
async def list_my_invites_route(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await list_my_invites(session, user.email)


@router.post("/invitations/{invite_id}/decline")
async def decline_invite_route(
    invite_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await decline_invite(session, invite_id, user.email)
    return SuccessResponse()


# ── Member lookup ─────────────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/users/lookup")
async def lookup_user_route(
    email: str,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await lookup_user_by_email(session, email)


# ── Member skills ─────────────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/members/{member_id}/skills")
async def list_skills_route(
    member_id: str,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    return await list_member_skills(session, ws.workspace_id, member_id)


@router.post("/workspaces/{workspace_id}/members/{member_id}/skills", status_code=201)
async def add_skill_route(
    member_id: str,
    data: MemberSkillCreate,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await add_member_skill(session, ws.workspace_id, member_id, data.skill_name, data.level)


@router.delete("/workspaces/{workspace_id}/members/{member_id}/skills/{skill_id}")
async def delete_skill_route(
    member_id: str,
    skill_id: str,
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_member_skill(session, ws.workspace_id, skill_id)
    return SuccessResponse()
