"""Workspace repositories — workspaces, members, invites, skills."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.workspace import Workspace, WorkspaceMember, WorkspaceInvite, MemberSkill
from shared.models.user import User


class WorkspaceRepository(BaseRepository):
    model = Workspace

    async def find_by_slug(self, slug: str) -> Workspace | None:
        result = await self.session.execute(
            select(Workspace).where(Workspace.slug == slug).limit(1)
        )
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
        result = await self.session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            .limit(1)
        )
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
            if not d.get("display_name"):
                d["display_name"] = full_name
            d["email"] = email
            rows.append(d)
        return rows


class WorkspaceInviteRepository(BaseRepository):
    model = WorkspaceInvite

    async def find_by_token(self, token: str) -> WorkspaceInvite | None:
        result = await self.session.execute(
            select(WorkspaceInvite).where(WorkspaceInvite.token == token).limit(1)
        )
        return result.scalar_one_or_none()

    async def find_pending(self, workspace_id: str) -> list[WorkspaceInvite]:
        result = await self.session.execute(
            select(WorkspaceInvite).where(
                WorkspaceInvite.workspace_id == workspace_id,
                WorkspaceInvite.accepted == False,
            ).order_by(WorkspaceInvite.created_at.desc())
        )
        return list(result.scalars().all())


class MemberSkillRepository(BaseRepository):
    model = MemberSkill

    async def find_by_member(self, workspace_id: str, member_id: str) -> list[MemberSkill]:
        result = await self.session.execute(
            select(MemberSkill).where(
                MemberSkill.workspace_id == workspace_id,
                MemberSkill.workspace_member_id == member_id,
            )
        )
        return list(result.scalars().all())
