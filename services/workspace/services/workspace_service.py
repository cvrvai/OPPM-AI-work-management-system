"""Workspace service — business logic for workspaces, members, invites, skills.
Migrated from services/core/services/workspace_service.py"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.models.workspace import Workspace, WorkspaceMember, WorkspaceInvite, MemberSkill
from shared.models.user import User
from repositories.workspace_repo import (
    WorkspaceRepository,
    WorkspaceMemberRepository,
    WorkspaceInviteRepository,
    MemberSkillRepository,
)

logger = logging.getLogger(__name__)


async def get_user_workspaces(session: AsyncSession, user_id: str) -> list[dict]:
    repo = WorkspaceRepository(session)
    return await repo.find_user_workspaces(user_id)


async def create_workspace(
    session: AsyncSession, user_id: str, name: str, slug: str, description: str = ""
) -> dict:
    repo = WorkspaceRepository(session)
    if await repo.find_by_slug(slug):
        raise HTTPException(status_code=409, detail="Workspace slug already taken")

    ws = await repo.create({"name": name, "slug": slug, "description": description, "created_by": user_id})
    # Add creator as owner
    member_repo = WorkspaceMemberRepository(session)
    await member_repo.create({"workspace_id": str(ws.id), "user_id": user_id, "role": "owner"})
    await session.commit()
    return {c.name: getattr(ws, c.name) for c in ws.__table__.columns}


async def get_workspace(session: AsyncSession, workspace_id: str, user_id: str) -> dict:
    repo = WorkspaceRepository(session)
    ws = await repo.find_by_id(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    member_repo = WorkspaceMemberRepository(session)
    member = await member_repo.find_by_user_and_workspace(user_id, workspace_id)
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    d = {c.name: getattr(ws, c.name) for c in ws.__table__.columns}
    d["current_user_role"] = member.role
    return d


async def update_workspace(session: AsyncSession, workspace_id: str, user_id: str, data: dict) -> dict:
    repo = WorkspaceRepository(session)
    ws = await repo.update(workspace_id, data)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await session.commit()
    return {c.name: getattr(ws, c.name) for c in ws.__table__.columns}


async def delete_workspace(session: AsyncSession, workspace_id: str, user_id: str) -> None:
    repo = WorkspaceRepository(session)
    deleted = await repo.delete(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await session.commit()


async def get_workspace_members(session: AsyncSession, workspace_id: str) -> list[dict]:
    repo = WorkspaceMemberRepository(session)
    return await repo.find_members(workspace_id)


async def update_member_role(
    session: AsyncSession, workspace_id: str, member_id: str, role: str, requester_id: str
) -> dict:
    repo = WorkspaceMemberRepository(session)
    member = await repo.update(member_id, {"role": role})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await session.commit()
    return dict(member)


async def remove_member(
    session: AsyncSession, workspace_id: str, member_id: str, requester_id: str
) -> None:
    repo = WorkspaceMemberRepository(session)
    deleted = await repo.delete(member_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Member not found")
    await session.commit()


async def update_my_display_name(
    session: AsyncSession, workspace_id: str, user_id: str, display_name: str
) -> dict:
    repo = WorkspaceMemberRepository(session)
    member = await repo.find_by_user_and_workspace(user_id, workspace_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    updated = await repo.update(str(member.id), {"display_name": display_name})
    await session.commit()
    return dict(updated)


async def create_invite(
    session: AsyncSession, workspace_id: str, email: str, role, inviter_id: str
) -> dict:
    token = secrets.token_urlsafe(32)
    invite_repo = WorkspaceInviteRepository(session)
    invite = await invite_repo.create({
        "workspace_id": workspace_id,
        "email": email,
        "role": role.value if hasattr(role, "value") else role,
        "token": token,
        "invited_by": inviter_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    })
    await session.commit()
    return {c.name: getattr(invite, c.name) for c in invite.__table__.columns}


async def accept_invite(session: AsyncSession, token: str, user_id: str) -> dict:
    invite_repo = WorkspaceInviteRepository(session)
    invite = await invite_repo.find_by_token(token)
    if not invite or invite.accepted:
        raise HTTPException(status_code=404, detail="Invitation not found or already used")

    member_repo = WorkspaceMemberRepository(session)
    existing = await member_repo.find_by_user_and_workspace(user_id, str(invite.workspace_id))
    if existing:
        raise HTTPException(status_code=409, detail="Already a member of this workspace")

    await member_repo.create({"workspace_id": str(invite.workspace_id), "user_id": user_id, "role": invite.role})
    invite.accepted = True
    await session.commit()
    return {"message": "Joined workspace", "workspace_id": str(invite.workspace_id)}


async def get_pending_invites(session: AsyncSession, workspace_id: str) -> list[dict]:
    repo = WorkspaceInviteRepository(session)
    invites = await repo.find_pending(workspace_id)
    return [{c.name: getattr(i, c.name) for c in i.__table__.columns} for i in invites]


async def revoke_invite(session: AsyncSession, workspace_id: str, invite_id: str) -> None:
    repo = WorkspaceInviteRepository(session)
    deleted = await repo.delete(invite_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Invite not found")
    await session.commit()


async def resend_invite(session: AsyncSession, workspace_id: str, invite_id: str) -> dict:
    repo = WorkspaceInviteRepository(session)
    invite = await repo.find_by_id(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    return {c.name: getattr(invite, c.name) for c in invite.__table__.columns}


async def lookup_user_by_email(session: AsyncSession, email: str) -> dict:
    result = await session.execute(select(User).where(User.email == email).limit(1))
    user = result.scalar_one_or_none()
    return {"exists": bool(user), "user_id": str(user.id) if user else None, "display_name": user.full_name if user else None}


async def get_invite_preview(session: AsyncSession, token: str) -> dict:
    invite_repo = WorkspaceInviteRepository(session)
    invite = await invite_repo.find_by_token(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found or expired")
    ws_repo = WorkspaceRepository(session)
    ws = await ws_repo.find_by_id(str(invite.workspace_id))
    return {
        "invite_id": str(invite.id),
        "workspace_id": str(invite.workspace_id),
        "workspace_name": ws.name if ws else "",
        "workspace_slug": ws.slug if ws else "",
        "role": invite.role,
        "expires_at": str(invite.expires_at),
    }


async def list_member_skills(session: AsyncSession, workspace_id: str, member_id: str) -> list[dict]:
    repo = MemberSkillRepository(session)
    skills = await repo.find_by_member(workspace_id, member_id)
    return [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in skills]


async def add_member_skill(session: AsyncSession, workspace_id: str, member_id: str, skill_name: str, level: str | None) -> dict:
    repo = MemberSkillRepository(session)
    skill = await repo.create({"workspace_id": workspace_id, "workspace_member_id": member_id, "skill_name": skill_name, "level": level})
    await session.commit()
    return {c.name: getattr(skill, c.name) for c in skill.__table__.columns}


async def delete_member_skill(session: AsyncSession, workspace_id: str, skill_id: str) -> None:
    repo = MemberSkillRepository(session)
    await repo.delete(skill_id)
    await session.commit()


async def list_my_invites(session: AsyncSession, email: str) -> list[dict]:
    result = await session.execute(
        select(WorkspaceInvite).where(WorkspaceInvite.email == email, WorkspaceInvite.accepted == False)
    )
    invites = result.scalars().all()
    return [{c.name: getattr(i, c.name) for c in i.__table__.columns} for i in invites]


async def decline_invite(session: AsyncSession, invite_id: str, email: str) -> None:
    result = await session.execute(
        select(WorkspaceInvite).where(WorkspaceInvite.id == invite_id, WorkspaceInvite.email == email).limit(1)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite.accepted = True  # mark as used / declined
    await session.commit()
