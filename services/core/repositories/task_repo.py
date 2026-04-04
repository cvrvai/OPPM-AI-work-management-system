"""Task repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.task import Task, TaskReport
from shared.models.project import Project


class TaskRepository(BaseRepository):
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

    async def find_by_objective(self, objective_id: str) -> list[Task]:
        return await self.find_all(
            filters={"oppm_objective_id": objective_id},
            order_by="created_at",
            desc=False,
        )

    async def get_project_progress_data(self, project_id: str) -> list[dict]:
        """Get progress + contribution for all tasks in a project (for weighted calc)."""
        stmt = (
            select(Task.progress, Task.project_contribution)
            .where(Task.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        return [{"progress": r.progress, "project_contribution": r.project_contribution} for r in result.all()]


class TaskReportRepository(BaseRepository):
    model = TaskReport

    async def find_by_task(self, task_id: str) -> list[TaskReport]:
        stmt = (
            select(TaskReport)
            .where(TaskReport.task_id == task_id)
            .order_by(TaskReport.report_date.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_total_hours(self, task_id: str) -> float:
        stmt = select(TaskReport.hours).where(TaskReport.task_id == task_id)
        result = await self.session.execute(stmt)
        return sum(r.hours for r in result.all())
