"""Project & project member repository."""

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.project import Project, ProjectMember
from shared.models.workspace import WorkspaceMember


class ProjectRepository(BaseRepository):
    model = Project

    async def find_workspace_projects(
        self,
        workspace_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Project]:
        stmt = select(Project).where(Project.workspace_id == workspace_id)
        if status:
            stmt = stmt.where(Project.status == status)
        stmt = stmt.order_by(Project.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_progress(self, project_id: str, progress: int) -> None:
        stmt = update(Project).where(Project.id == project_id).values(progress=progress)
        await self.session.execute(stmt)
        await self.session.flush()


class ProjectMemberRepository(BaseRepository):
    model = ProjectMember

    async def find_project_members(self, project_id: str) -> list[dict]:
        stmt = (
            select(ProjectMember, WorkspaceMember)
            .join(WorkspaceMember, WorkspaceMember.id == ProjectMember.member_id)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.joined_at)
        )
        result = await self.session.execute(stmt)
        members = []
        for pm, wm in result.all():
            d = {c.name: getattr(pm, c.name) for c in pm.__table__.columns}
            d["workspace_members"] = {
                "id": str(wm.id),
                "display_name": wm.display_name,
                "avatar_url": wm.avatar_url,
                "user_id": str(wm.user_id),
                "role": wm.role,
            }
            members.append(d)
        return members

    async def add_member(self, project_id: str, member_id: str, role: str = "contributor") -> ProjectMember:
        return await self.create({
            "project_id": project_id,
            "member_id": member_id,
            "role": role,
        })

    async def remove_member(self, project_id: str, member_id: str) -> bool:
        stmt = delete(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.member_id == member_id,
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return True
