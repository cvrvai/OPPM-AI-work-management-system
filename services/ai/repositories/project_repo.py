"""Project repository for AI service."""

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

    async def create_project(self, data: dict) -> Project:
        """Create a new project with defaults for optional fields."""
        defaults: dict = {
            "status": "planning",
            "priority": "medium",
            "progress": 0,
        }
        defaults.update(data)
        return await self.create(defaults)
