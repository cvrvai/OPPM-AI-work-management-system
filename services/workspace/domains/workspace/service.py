"""
Workspace service — business logic for workspace management.
"""

import secrets
from datetime import datetime, timezone, timedelta
import logging
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from shared.auth import invalidate_membership_cache
from shared.models.user import User
from shared.models.workspace import Workspace, WorkspaceMember, WorkspaceInvite
from domains.workspace.repository import (
    WorkspaceRepository,
    WorkspaceMemberRepository,
    WorkspaceInviteRepository,
    MemberSkillRepository,
)
from domains.notification.repository import AuditRepository
from infrastructure.email import send_invite_email

logger = logging.getLogger(__name__)


async def create_workspace(session: AsyncSession, user_id: str, name: str, slug: str, description: str = "") -> dict:
    """Create a workspace and add the creator as owner."""
    workspace_repo = WorkspaceRepository(session)
    member_repo = WorkspaceMemberRepository(session)
    audit_repo = AuditRepository(session)

    existing = await workspace_repo.find_by_slug(slug)
    if existing:
        raise HTTPException(status_code=400, detail="Workspace slug already taken")

    ws = await workspace_repo.create({
        "name": name,
        "slug": slug,
        "description": description,
        "created_by": user_id,
    })

    await member_repo.create({
        "workspace_id": str(ws.id),
        "user_id": user_id,
        "role": "owner",
    })

    await audit_repo.log(str(ws.id), user_id, "create", "workspace", str(ws.id), new_data={"name": name})
    return ws


async def get_user_workspaces(session: AsyncSession, user_id: str) -> list[dict]:
    workspace_repo = WorkspaceRepository(session)
    return await workspace_repo.find_user_workspaces(user_id)


async def get_workspace(session: AsyncSession, workspace_id: str, user_id: str) -> dict:
    workspace_repo = WorkspaceRepository(session)
    member_repo = WorkspaceMemberRepository(session)
    ws = await workspace_repo.find_by_id(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    member = await member_repo.find_by_user_and_workspace(user_id, workspace_id)
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    d = ws.to_dict()
    d["current_user_role"] = member.role
    return d


async def update_workspace(session: AsyncSession, workspace_id: str, user_id: str, data: dict) -> dict:
    workspace_repo = WorkspaceRepository(session)
    audit_repo = AuditRepository(session)

    result = await workspace_repo.update(workspace_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await audit_repo.log(workspace_id, user_id, "update", "workspace", workspace_id, new_data=data)
    return result


async def delete_workspace(session: AsyncSession, workspace_id: str, user_id: str) -> bool:
    workspace_repo = WorkspaceRepository(session)
    audit_repo = AuditRepository(session)

    await audit_repo.log(workspace_id, user_id, "delete", "workspace", workspace_id)
    return await workspace_repo.delete(workspace_id)


async def get_workspace_members(session: AsyncSession, workspace_id: str) -> list[dict]:
    member_repo = WorkspaceMemberRepository(session)
    return await member_repo.find_members(workspace_id)


async def update_member_role(session: AsyncSession, workspace_id: str, member_id: str, new_role: str, actor_id: str) -> dict:
    member_repo = WorkspaceMemberRepository(session)
    audit_repo = AuditRepository(session)

    member = await member_repo.find_by_id(member_id)
    if not member or str(member.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner" and new_role != "owner":
        owners = [m for m in await member_repo.find_members(workspace_id) if m["role"] == "owner"]
        if len(owners) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner")
    result = await member_repo.update(member_id, {"role": new_role})
    invalidate_membership_cache(str(member.user_id), workspace_id)
    await audit_repo.log(workspace_id, actor_id, "update_role", "workspace_member", member_id, new_data={"role": new_role})
    return result


async def remove_member(session: AsyncSession, workspace_id: str, member_id: str, actor_id: str) -> bool:
    member_repo = WorkspaceMemberRepository(session)
    audit_repo = AuditRepository(session)

    member = await member_repo.find_by_id(member_id)
    if not member or str(member.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the workspace owner")
    await audit_repo.log(workspace_id, actor_id, "remove", "workspace_member", member_id)
    invalidate_membership_cache(str(member.user_id), workspace_id)
    return await member_repo.delete(member_id)


async def update_my_display_name(session: AsyncSession, workspace_id: str, user_id: str, display_name: str) -> dict:
    """Update the current user's display_name in workspace_members."""
    member_repo = WorkspaceMemberRepository(session)

    member = await member_repo.find_by_user_and_workspace(user_id, workspace_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    result = await member_repo.update(member["id"], {"display_name": display_name})
    if not result:
        raise HTTPException(status_code=500, detail="Failed to update display name")
    return result


async def create_invite(session: AsyncSession, workspace_id: str, email: str, role: str, invited_by: str) -> dict:
    workspace_repo = WorkspaceRepository(session)
    member_repo = WorkspaceMemberRepository(session)
    invite_repo = WorkspaceInviteRepository(session)
    audit_repo = AuditRepository(session)

    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    # Check if user has an account via direct query
    result = await session.execute(select(User).where(User.email == email).limit(1))
    has_account = result.scalar_one_or_none() is not None

    invite = await invite_repo.create({
        "workspace_id": workspace_id,
        "email": email,
        "role": role,
        "invited_by": invited_by,
        "token": token,
        "expires_at": expires_at,
    })
    await audit_repo.log(workspace_id, invited_by, "invite", "workspace_invite", str(invite.id), new_data={"email": email})

    ws = await workspace_repo.find_by_id(workspace_id)
    ws_name = ws.name if ws else "a workspace"
    inviter_member = await member_repo.find_by_user_and_workspace(invited_by, workspace_id)
    inviter_display = inviter_member.get("display_name", "") if inviter_member else ""
    send_invite_email(email, ws_name, inviter_display or invited_by, token, role)

    return invite


async def accept_invite(session: AsyncSession, token: str, user_id: str) -> dict:
    workspace_repo = WorkspaceRepository(session)
    member_repo = WorkspaceMemberRepository(session)
    invite_repo = WorkspaceInviteRepository(session)

    invite = await invite_repo.find_by_token(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="Invite already accepted")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite has expired")

    existing = await member_repo.find_by_user_and_workspace(user_id, str(invite.workspace_id))
    if existing:
        raise HTTPException(status_code=400, detail="Already a member of this workspace")

    await member_repo.create({
        "workspace_id": str(invite.workspace_id),
        "user_id": user_id,
        "role": invite.role,
    })

    await invite_repo.update(str(invite.id), {"accepted_at": datetime.now(timezone.utc)})

    ws = await workspace_repo.find_by_id(str(invite.workspace_id))
    return {"workspace_id": str(invite.workspace_id), "workspace_name": ws.name if ws else ""}


async def get_pending_invites(session: AsyncSession, workspace_id: str) -> list[dict]:
    """Return pending (not accepted, not expired) invites for a workspace."""
    invite_repo = WorkspaceInviteRepository(session)
    return await invite_repo.find_pending(workspace_id)


async def revoke_invite(session: AsyncSession, workspace_id: str, invite_id: str, actor_id: str) -> bool:
    """Delete a pending invite."""
    invite_repo = WorkspaceInviteRepository(session)
    audit_repo = AuditRepository(session)

    invite = await invite_repo.find_by_id(invite_id)
    if not invite or str(invite.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="Cannot revoke an accepted invite")
    await audit_repo.log(workspace_id, actor_id, "revoke_invite", "workspace_invite", invite_id)
    return await invite_repo.delete(invite_id)


async def lookup_user_by_email(session: AsyncSession, workspace_id: str, email: str) -> dict:
    """Check if email has an account and whether they're already a workspace member."""
    member_repo = WorkspaceMemberRepository(session)

    result = await session.execute(
        select(User.id, User.full_name).where(User.email == email).limit(1)
    )
    row = result.first()
    if not row:
        return {"exists": False, "user_id": None, "display_name": None, "already_member": False}

    existing = await member_repo.find_by_user_and_workspace(str(row.id), workspace_id)
    return {
        "exists": True,
        "user_id": str(row.id),
        "display_name": row.full_name,
        "already_member": existing is not None,
    }


async def get_invite_preview(session: AsyncSession, token: str) -> dict:
    """Public endpoint — return workspace preview for an invite token."""
    result = await session.execute(
        select(
            WorkspaceInvite.id.label("invite_id"),
            Workspace.id.label("workspace_id"),
            Workspace.name.label("workspace_name"),
            Workspace.slug.label("workspace_slug"),
            WorkspaceMember.display_name.label("inviter_name"),
            WorkspaceInvite.role,
            WorkspaceInvite.expires_at,
            WorkspaceInvite.accepted_at,
        )
        .join(Workspace, WorkspaceInvite.workspace_id == Workspace.id)
        .outerjoin(
            WorkspaceMember,
            WorkspaceInvite.invited_by == WorkspaceMember.user_id,
        )
        .where(WorkspaceInvite.token == token)
        .limit(1)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Invite not found")

    # Count workspace members
    count_result = await session.execute(
        select(func.count(WorkspaceMember.id)).where(WorkspaceMember.workspace_id == row.workspace_id)
    )
    member_count = count_result.scalar_one()

    expires_at = row.expires_at
    return {
        "invite_id": str(row.invite_id),
        "workspace_id": str(row.workspace_id),
        "workspace_name": row.workspace_name,
        "workspace_slug": row.workspace_slug,
        "inviter_name": row.inviter_name or "",
        "role": row.role,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "accepted_at": row.accepted_at.isoformat() if row.accepted_at else None,
        "member_count": member_count,
        "is_expired": expires_at is not None and expires_at < datetime.now(timezone.utc),
        "is_accepted": row.accepted_at is not None,
    }


async def resend_invite(session: AsyncSession, workspace_id: str, invite_id: str, actor_id: str) -> dict:
    """Regenerate token + expiry and re-send the invite email."""
    workspace_repo = WorkspaceRepository(session)
    member_repo = WorkspaceMemberRepository(session)
    invite_repo = WorkspaceInviteRepository(session)
    audit_repo = AuditRepository(session)

    invite = await invite_repo.find_by_id(invite_id)
    if not invite or str(invite.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="Invite already accepted")

    new_token = secrets.token_urlsafe(48)
    new_expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    updated = await invite_repo.update(invite_id, {
        "token": new_token,
        "expires_at": new_expires,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })

    ws = await workspace_repo.find_by_id(workspace_id)
    ws_name = ws.name if ws else "a workspace"
    inviter_member = await member_repo.find_by_user_and_workspace(actor_id, workspace_id)
    inviter_display = inviter_member.get("display_name", "") if inviter_member else ""
    send_invite_email(invite.email, ws_name, inviter_display or actor_id, new_token, invite.role)

    await audit_repo.log(workspace_id, actor_id, "resend_invite", "workspace_invite", invite_id)
    return updated


# ── Member Skills ──

async def list_member_skills(session: AsyncSession, workspace_id: str, workspace_member_id: str) -> list[dict]:
    """Return all skills for a workspace member."""
    skill_repo = MemberSkillRepository(session)
    member_repo = WorkspaceMemberRepository(session)

    member = await member_repo.find_by_id(workspace_member_id)
    if not member or str(member.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")
    return await skill_repo.find_by_member(workspace_member_id)


async def add_member_skill(session: AsyncSession, workspace_id: str, workspace_member_id: str, skill_name: str, skill_level: str, actor_id: str, is_admin: bool) -> dict:
    """Add a skill to a workspace member. Members can only add to their own; admins can add to any."""
    skill_repo = MemberSkillRepository(session)
    member_repo = WorkspaceMemberRepository(session)

    member = await member_repo.find_by_id(workspace_member_id)
    if not member or str(member.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")

    actor_member = await member_repo.find_by_user_and_workspace(actor_id, workspace_id)
    if not actor_member:
        raise HTTPException(status_code=403, detail="Not a workspace member")
    if not is_admin and str(actor_member["id"]) != workspace_member_id:
        raise HTTPException(status_code=403, detail="Cannot add skills to another member")

    skill = await skill_repo.create({
        "workspace_member_id": workspace_member_id,
        "skill_name": skill_name,
        "skill_level": skill_level,
    })
    return dict(skill)


async def delete_member_skill(session: AsyncSession, workspace_id: str, workspace_member_id: str, skill_id: str, actor_id: str, is_admin: bool) -> bool:
    """Delete a skill. Members can only delete their own; admins can delete any."""
    skill_repo = MemberSkillRepository(session)
    member_repo = WorkspaceMemberRepository(session)

    member = await member_repo.find_by_id(workspace_member_id)
    if not member or str(member.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Member not found")

    actor_member = await member_repo.find_by_user_and_workspace(actor_id, workspace_id)
    if not actor_member:
        raise HTTPException(status_code=403, detail="Not a workspace member")
    if not is_admin and str(actor_member["id"]) != workspace_member_id:
        raise HTTPException(status_code=403, detail="Cannot delete skills of another member")

    skill = await skill_repo.find_by_id(skill_id)
    if not skill or str(skill.workspace_member_id) != workspace_member_id:
        raise HTTPException(status_code=404, detail="Skill not found")
    return await skill_repo.delete(skill_id)


# ── User invite inbox ──

async def list_my_invites(session: AsyncSession, user_email: str) -> list[dict]:
    """Return all pending invites addressed to the current user's email."""
    invite_repo = WorkspaceInviteRepository(session)
    workspace_repo = WorkspaceRepository(session)
    member_repo = WorkspaceMemberRepository(session)

    invites = await invite_repo.find_pending_by_email(user_email)
    now = datetime.now(timezone.utc)
    result = []
    for invite in invites:
        ws = await workspace_repo.find_by_id(str(invite.workspace_id))
        if not ws:
            continue
        inviter_member = await member_repo.find_by_user_and_workspace(
            str(invite.invited_by), str(invite.workspace_id)
        )
        inviter_display = ""
        if inviter_member:
            inviter_display = inviter_member.get("display_name") or inviter_member.get("email", "")
        result.append({
            "id": str(invite.id),
            "workspace_id": str(invite.workspace_id),
            "workspace_name": ws.name,
            "workspace_slug": ws.slug,
            "inviter_name": inviter_display,
            "role": invite.role,
            "token": invite.token,
            "expires_at": invite.expires_at.isoformat(),
            "created_at": invite.created_at.isoformat(),
            "is_expired": invite.expires_at < now,
        })
    return result


async def sync_members_to_workspace(session: AsyncSession, workspace_id: str, members_data: list[dict]) -> list[dict]:
    """Upsert Supabase team members into workspace_members by email lookup.

    For each entry: find the OPPM user by email, then create a workspace_member
    row if one does not already exist.  Members whose email is not yet in the
    OPPM users table (they haven't logged in yet) are returned with synced=False.
    """
    member_repo = WorkspaceMemberRepository(session)
    results = []

    for item in members_data:
        email = (item.get("email") or "").strip().lower()
        if not email:
            continue

        display_name = item.get("display_name") or None
        role = item.get("role") or "member"

        # Look up user by email in the OPPM users table
        user_result = await session.execute(select(User).where(User.email == email).limit(1))
        user = user_result.scalar_one_or_none()

        if not user:
            # Auto-create a stub user record so Supabase-sourced members can be
            # added to workspaces/projects/tasks even before they ever log in
            # to OPPM. They cannot authenticate locally (placeholder password);
            # if they log in via Supabase SSO, the OPPM auth flow should match
            # them by email or by (auth_provider, external_subject).
            user = User(
                email=email,
                hashed_password="!supabase-stub",  # disabled local password
                auth_provider="supabase",
                full_name=display_name,
                is_active=True,
                is_verified=False,
            )
            session.add(user)
            await session.flush()  # populate user.id

        # Already a workspace member?
        existing = await member_repo.find_by_user_and_workspace(str(user.id), workspace_id)
        if existing:
            wm_id = str(existing.id) if hasattr(existing, "id") else str(existing["id"])
            results.append({"email": email, "workspace_member_id": wm_id, "synced": True, "reason": "already_member"})
            continue

        # Add to workspace — normalize role to a valid workspace role value
        _VALID_ROLES = {"owner", "admin", "member", "viewer"}
        ws_role = role if role in _VALID_ROLES else "member"
        new_member = await member_repo.create({
            "workspace_id": workspace_id,
            "user_id": str(user.id),
            "role": ws_role,
            "display_name": display_name or user.full_name,
            "avatar_url": user.avatar_url,
        })
        results.append({"email": email, "workspace_member_id": str(new_member.id), "synced": True, "reason": "added"})

    return results


async def decline_invite(session: AsyncSession, invite_id: str, user_email: str) -> None:
    """Decline (delete) a pending invite. User may only decline their own invites."""
    invite_repo = WorkspaceInviteRepository(session)

    invite = await invite_repo.find_by_id(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.email.lower() != user_email.lower():
        raise HTTPException(status_code=403, detail="Not authorized to decline this invite")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="Invite already accepted")
    await invite_repo.delete(invite_id)
