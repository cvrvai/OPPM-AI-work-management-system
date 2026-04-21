"""Workspace & workspace member repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.workspace import Workspace, WorkspaceMember, WorkspaceInvite, MemberSkill
from shared.models.user import User


class WorkspaceRepository(BaseRepository):
    model = Workspace

    async def find_by_slug(self, slug: str) -> Workspace | None:
        stmt = select(Workspace).where(Workspace.slug == slug).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_user_workspaces(self, user_id: str) -> list[dict]:
        stmt = (
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.name)
        )
        result = await self.session.execute(stmt)
        workspaces = []
        for ws, role in result.all():
            d = {c.name: getattr(ws, c.name) for c in ws.__table__.columns}
            d["current_user_role"] = role
            workspaces.append(d)
        return workspaces


class WorkspaceMemberRepository(BaseRepository):
    model = WorkspaceMember

    async def find_by_user_and_workspace(self, user_id: str, workspace_id: str) -> WorkspaceMember | None:
        stmt = (
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_members(self, workspace_id: str) -> list[dict]:
        stmt = (
            select(WorkspaceMember, User.email, User.full_name)
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at.asc())
        )
        result = await self.session.execute(stmt)
        rows = []
        for member, email, full_name in result.all():
            d = dict(member)
            # Populate display_name from user's full_name if not set in workspace
            if not d.get("display_name"):
                d["display_name"] = full_name
            d["email"] = email
            rows.append(d)
        return rows


class WorkspaceInviteRepository(BaseRepository):
    model = WorkspaceInvite

    async def find_by_token(self, token: str) -> WorkspaceInvite | None:
        stmt = select(WorkspaceInvite).where(WorkspaceInvite.token == token).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_pending(self, workspace_id: str) -> list[WorkspaceInvite]:
        stmt = (
            select(WorkspaceInvite)
            .where(
                WorkspaceInvite.workspace_id == workspace_id,
                WorkspaceInvite.accepted_at.is_(None),
            )
            .order_by(WorkspaceInvite.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_pending_by_email(self, email: str) -> list[WorkspaceInvite]:
        stmt = (
            select(WorkspaceInvite)
            .where(
                WorkspaceInvite.email == email,
                WorkspaceInvite.accepted_at.is_(None),
            )
            .order_by(WorkspaceInvite.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class MemberSkillRepository(BaseRepository):
    model = MemberSkill

    async def find_by_member(self, workspace_member_id: str) -> list[dict]:
        stmt = (
            select(MemberSkill)
            .where(MemberSkill.workspace_member_id == workspace_member_id)
            .order_by(MemberSkill.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return [dict(s) for s in result.scalars().all()]
