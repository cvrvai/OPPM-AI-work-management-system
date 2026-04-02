"""Workspace routes — CRUD, members, invites."""

from fastapi import APIRouter, Depends
from shared.auth import CurrentUser, get_current_user, WorkspaceContext, get_workspace_context, require_admin
from schemas.workspace import WorkspaceCreate, WorkspaceUpdate, MemberUpdate, InviteCreate, InviteAccept, DisplayNameUpdate
from shared.schemas.common import SuccessResponse
from services.workspace_service import (
    create_workspace,
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
)

router = APIRouter()


# ── Workspace CRUD ──

@router.get("/workspaces")
async def list_workspaces(user: CurrentUser = Depends(get_current_user)):
    return get_user_workspaces(user.id)


@router.post("/workspaces", status_code=201)
async def create_workspace_route(data: WorkspaceCreate, user: CurrentUser = Depends(get_current_user)):
    return create_workspace(user.id, data.name, data.slug, data.description)


@router.put("/workspaces/{workspace_id}")
async def update_workspace_route(data: WorkspaceUpdate, ws: WorkspaceContext = Depends(require_admin)):
    return update_workspace(ws.workspace_id, ws.user.id, data.model_dump(exclude_none=True))


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace_route(ws: WorkspaceContext = Depends(require_admin)) -> SuccessResponse:
    delete_workspace(ws.workspace_id, ws.user.id)
    return SuccessResponse()


# ── Members ──

@router.get("/workspaces/{workspace_id}/members")
async def list_members(ws: WorkspaceContext = Depends(get_workspace_context)):
    return get_workspace_members(ws.workspace_id)


@router.put("/workspaces/{workspace_id}/members/{member_id}")
async def update_member(member_id: str, data: MemberUpdate, ws: WorkspaceContext = Depends(require_admin)):
    return update_member_role(ws.workspace_id, member_id, data.role.value, ws.user.id)


@router.delete("/workspaces/{workspace_id}/members/{member_id}")
async def remove_member_route(member_id: str, ws: WorkspaceContext = Depends(require_admin)) -> SuccessResponse:
    remove_member(ws.workspace_id, member_id, ws.user.id)
    return SuccessResponse()


@router.patch("/workspaces/{workspace_id}/members/me/display-name")
async def update_my_display_name_route(
    data: DisplayNameUpdate,
    ws: WorkspaceContext = Depends(get_workspace_context),
):
    """Update the current user's display name in this workspace."""
    return update_my_display_name(ws.workspace_id, ws.user.id, data.display_name)


# ── Invites ──

@router.get("/workspaces/{workspace_id}/invites")
async def list_invites(ws: WorkspaceContext = Depends(require_admin)):
    return get_pending_invites(ws.workspace_id)


@router.post("/workspaces/{workspace_id}/invites", status_code=201)
async def create_invite_route(data: InviteCreate, ws: WorkspaceContext = Depends(require_admin)):
    return create_invite(ws.workspace_id, data.email, data.role.value, ws.user.id)


@router.delete("/workspaces/{workspace_id}/invites/{invite_id}")
async def revoke_invite_route(invite_id: str, ws: WorkspaceContext = Depends(require_admin)) -> SuccessResponse:
    revoke_invite(ws.workspace_id, invite_id, ws.user.id)
    return SuccessResponse()


@router.post("/invites/accept")
async def accept_invite_route(data: InviteAccept, user: CurrentUser = Depends(get_current_user)):
    return accept_invite(data.token, user.id)
