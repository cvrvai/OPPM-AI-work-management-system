"""Minimal task repository for intelligence service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.task import Task
from shared.models.project import Project
from repositories.base import BaseRepository


class TaskRepository(BaseRepository):
    """Task repo with CRUD + workspace/project listings."""

    model = Task

    async def find_workspace_tasks(
        self,
        workspace_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        stmt = (
            select(Task)
            .join(Project, Project.id == Task.project_id)
            .where(Project.workspace_id == workspace_id)
        )
        if status:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_project_tasks(
        self,
        project_id: str,
        status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Task]:
        stmt = select(Task).where(Task.project_id == project_id)
        if status:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.created_at.desc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
