"""Task repository (read-only) for AI service — used for commit analysis context."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.task import Task


class TaskRepository(BaseRepository):
    model = Task

    async def find_project_tasks(self, project_id: str, limit: int = 500) -> list[Task]:
        stmt = (
            select(Task)
            .where(Task.project_id == project_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
