"""Workspace routes — CRUD, members, invites."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import CurrentUser, get_current_user, WorkspaceContext, get_workspace_context, require_admin, require_owner, require_write
from shared.database import get_session
from domains.workspace.schemas import WorkspaceCreate, WorkspaceUpdate, MemberUpdate, InviteCreate, InviteAccept, DisplayNameUpdate, MemberSkillCreate, SyncMembersRequest
from shared.schemas.common import SuccessResponse
from domains.workspace.service import (
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
    sync_members_to_workspace,
)

router = APIRouter()


# ── Workspace CRUD ──

@router.get("/workspaces")
async def list_workspaces(user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await get_user_workspaces(session, user.id)


@router.post("/workspaces", status_code=201)
async def create_workspace_route(data: WorkspaceCreate, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await create_workspace(session, user.id, data.name, data.slug, data.description)


@router.get("/workspaces/{workspace_id}")
async def get_workspace_route(workspace_id: str, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await get_workspace(session, workspace_id, user.id)


@router.put("/workspaces/{workspace_id}")
async def update_workspace_route(data: WorkspaceUpdate, ws: WorkspaceContext = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    return await update_workspace(session, ws.workspace_id, ws.user.id, data.model_dump(exclude_none=True))


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace_route(ws: WorkspaceContext = Depends(require_owner), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await delete_workspace(session, ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Members ──

@router.get("/workspaces/{workspace_id}/members")
async def list_members(ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await get_workspace_members(session, ws.workspace_id)


@router.put("/workspaces/{workspace_id}/members/{member_id}")
async def update_member(member_id: str, data: MemberUpdate, ws: WorkspaceContext = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    return await update_member_role(session, ws.workspace_id, member_id, data.role.value, ws.user.id)


@router.delete("/workspaces/{workspace_id}/members/{member_id}")
async def remove_member_route(member_id: str, ws: WorkspaceContext = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await remove_member(session, ws.workspace_id, member_id, ws.user.id)
    return SuccessResponse()


@router.patch("/workspaces/{workspace_id}/members/me/display-name")
async def update_my_display_name_route(
    data: DisplayNameUpdate,
    ws: WorkspaceContext = Depends(get_workspace_context),
    session: AsyncSession = Depends(get_session),
):
    """Update the current user's display name in this workspace."""
    return await update_my_display_name(session, ws.workspace_id, ws.user.id, data.display_name)


# ── Invites ──

@router.get("/workspaces/{workspace_id}/invites")
async def list_invites(ws: WorkspaceContext = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    return await get_pending_invites(session, ws.workspace_id)


@router.post("/workspaces/{workspace_id}/invites", status_code=201)
async def create_invite_route(data: InviteCreate, ws: WorkspaceContext = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    return await create_invite(session, ws.workspace_id, data.email, data.role.value, ws.user.id)


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}")
async def revoke_invite_route(invite_id: str, ws: WorkspaceContext = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await revoke_invite(session, ws.workspace_id, invite_id, ws.user.id)
    return SuccessResponse()


@router.post("/workspaces/{workspace_id}/invites/{invite_id}/resend", status_code=200)
async def resend_invite_route(invite_id: str, ws: WorkspaceContext = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    return await resend_invite(session, ws.workspace_id, invite_id, ws.user.id)


@router.post("/workspaces/{workspace_id}/members/sync")
async def sync_members_route(data: SyncMembersRequest, ws: WorkspaceContext = Depends(require_write), session: AsyncSession = Depends(get_session)):
    """Upsert Supabase members into the OPPM workspace_members table by email.
    Returns per-member sync status including the resolved workspace_member_id.
    Allowed for any workspace writer (owner/admin/member) — this only adds users
    by email and is idempotent.
    """
    return await sync_members_to_workspace(session, ws.workspace_id, [m.model_dump() for m in data.members])


@router.get("/workspaces/{workspace_id}/members/lookup")
async def lookup_member_route(
    email: str = Query(..., min_length=3, max_length=255),
    ws: WorkspaceContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await lookup_user_by_email(session, ws.workspace_id, email)


@router.post("/invites/accept")
async def accept_invite_route(data: InviteAccept, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await accept_invite(session, data.token, user.id)


@router.get("/invites/my-invites")
async def list_my_invites_route(user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Return all pending workspace invites addressed to the current user's email."""
    return await list_my_invites(session, user.email)


@router.post("/invites/{invite_id}/decline")
async def decline_invite_route(invite_id: str, user: CurrentUser = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    await decline_invite(session, invite_id, user.email)
    return SuccessResponse()


@router.get("/invites/preview/{token}")
async def invite_preview_route(token: str, session: AsyncSession = Depends(get_session)):
    """Public — no auth required. Returns workspace preview for the invite."""
    return await get_invite_preview(session, token)


# ── Member Skills ──

@router.get("/workspaces/{workspace_id}/members/{member_id}/skills")
async def list_skills_route(member_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    return await list_member_skills(session, ws.workspace_id, member_id)


@router.post("/workspaces/{workspace_id}/members/{member_id}/skills", status_code=201)
async def add_skill_route(member_id: str, data: MemberSkillCreate, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)):
    is_admin = ws.role in ("owner", "admin")
    return await add_member_skill(session, ws.workspace_id, member_id, data.skill_name, data.skill_level, ws.user.id, is_admin)


@router.delete("/workspaces/{workspace_id}/members/{member_id}/skills/{skill_id}")
async def delete_skill_route(member_id: str, skill_id: str, ws: WorkspaceContext = Depends(get_workspace_context), session: AsyncSession = Depends(get_session)) -> SuccessResponse:
    is_admin = ws.role in ("owner", "admin")
    await delete_member_skill(session, ws.workspace_id, member_id, skill_id, ws.user.id, is_admin)
    return SuccessResponse()
