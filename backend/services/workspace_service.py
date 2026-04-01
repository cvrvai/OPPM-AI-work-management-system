"""
Workspace service — business logic for workspace management.
"""

import secrets
from datetime import datetime, timezone, timedelta
import logging
from fastapi import HTTPException, status
from repositories.workspace_repo import (
    WorkspaceRepository,
    WorkspaceMemberRepository,
    WorkspaceInviteRepository,
)
from repositories.notification_repo import AuditRepository
from infrastructure.email import send_invite_email

logger = logging.getLogger(__name__)

workspace_repo = WorkspaceRepository()
member_repo = WorkspaceMemberRepository()
invite_repo = WorkspaceInviteRepository()
audit_repo = AuditRepository()


def create_workspace(user_id: str, name: str, slug: str, description: str = "") -> dict:
    """Create a workspace and add the creator as owner."""
    existing = workspace_repo.find_by_slug(slug)
    if existing:
        raise HTTPException(status_code=400, detail="Workspace slug already taken")

    ws = workspace_repo.create({
        "name": name,
        "slug": slug,
        "description": description,
        "created_by": user_id,
    })

    # Add creator as owner
    member_repo.create({
        "workspace_id": ws["id"],
        "user_id": user_id,
        "role": "owner",
    })

    audit_repo.log(ws["id"], user_id, "create", "workspace", ws["id"], new_data={"name": name})
    return ws


def get_user_workspaces(user_id: str) -> list[dict]:
    return workspace_repo.find_user_workspaces(user_id)


def update_workspace(workspace_id: str, user_id: str, data: dict) -> dict:
    result = workspace_repo.update(workspace_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Workspace not found")
    audit_repo.log(workspace_id, user_id, "update", "workspace", workspace_id, new_data=data)
    return result


def delete_workspace(workspace_id: str, user_id: str) -> bool:
    audit_repo.log(workspace_id, user_id, "delete", "workspace", workspace_id)
    return workspace_repo.delete(workspace_id)


def get_workspace_members(workspace_id: str) -> list[dict]:
    return member_repo.find_members(workspace_id)


def update_member_role(workspace_id: str, member_id: str, new_role: str, actor_id: str) -> dict:
    member = member_repo.find_by_id(member_id)
    if not member or member["workspace_id"] != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if member["role"] == "owner" and new_role != "owner":
        # Prevent demoting the last owner
        owners = [m for m in member_repo.find_members(workspace_id) if m["role"] == "owner"]
        if len(owners) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner")
    result = member_repo.update(member_id, {"role": new_role})
    audit_repo.log(workspace_id, actor_id, "update_role", "workspace_member", member_id, new_data={"role": new_role})
    return result


def remove_member(workspace_id: str, member_id: str, actor_id: str) -> bool:
    member = member_repo.find_by_id(member_id)
    if not member or member["workspace_id"] != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if member["role"] == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the workspace owner")
    audit_repo.log(workspace_id, actor_id, "remove", "workspace_member", member_id)
    return member_repo.delete(member_id)


def update_my_display_name(workspace_id: str, user_id: str, display_name: str) -> dict:
    """Update the current user's display_name in workspace_members."""
    member = member_repo.find_by_user_and_workspace(user_id, workspace_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    result = member_repo.update(member["id"], {"display_name": display_name})
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update display name")
    return result


def create_invite(workspace_id: str, email: str, role: str, invited_by: str) -> dict:
    token = secrets.token_urlsafe(48)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    invite = invite_repo.create({
        "workspace_id": workspace_id,
        "email": email,
        "role": role,
        "invited_by": invited_by,
        "token": token,
        "expires_at": expires_at,
    })
    audit_repo.log(workspace_id, invited_by, "invite", "workspace_invite", invite["id"], new_data={"email": email})

    # Send invite email (non-blocking — invite succeeds even if email fails)
    ws = workspace_repo.find_by_id(workspace_id)
    ws_name = ws["name"] if ws else "a workspace"
    # Use invited_by ID to look up email from member record
    inviter_member = member_repo.find_by_user_and_workspace(invited_by, workspace_id)
    inviter_display = inviter_member.get("display_name", "") if inviter_member else ""
    send_invite_email(email, ws_name, inviter_display or invited_by, token, role)

    return invite


def accept_invite(token: str, user_id: str) -> dict:
    invite = invite_repo.find_by_token(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite["accepted_at"]:
        raise HTTPException(status_code=400, detail="Invite already accepted")
    if datetime.fromisoformat(invite["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite has expired")

    # Add user as member
    existing = member_repo.find_by_user_and_workspace(user_id, invite["workspace_id"])
    if existing:
        raise HTTPException(status_code=400, detail="Already a member of this workspace")

    member_repo.create({
        "workspace_id": invite["workspace_id"],
        "user_id": user_id,
        "role": invite["role"],
    })

    # Mark invite as accepted
    invite_repo.update(invite["id"], {"accepted_at": datetime.now(timezone.utc).isoformat()})

    ws = workspace_repo.find_by_id(invite["workspace_id"])
    return {"workspace_id": invite["workspace_id"], "workspace_name": ws["name"] if ws else ""}


def get_pending_invites(workspace_id: str) -> list[dict]:
    """Return pending (not accepted, not expired) invites for a workspace."""
    return invite_repo.find_pending(workspace_id)


def revoke_invite(workspace_id: str, invite_id: str, actor_id: str) -> bool:
    """Delete a pending invite."""
    invite = invite_repo.find_by_id(invite_id)
    if not invite or invite["workspace_id"] != workspace_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite["accepted_at"]:
        raise HTTPException(status_code=400, detail="Cannot revoke an accepted invite")
    audit_repo.log(workspace_id, actor_id, "revoke_invite", "workspace_invite", invite_id)
    return invite_repo.delete(invite_id)
