"""Project repository (read-only) for AI service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.project import Project


class ProjectRepository(BaseRepository):
    model = Project

    async def find_workspace_projects(self, workspace_id: str, limit: int = 500) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
