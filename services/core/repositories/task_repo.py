"""Task repository."""

from sqlalchemy import select, delete, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.task import Task, TaskReport, TaskDependency
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

    async def get_dependencies(self, task_id: str) -> list[str]:
        """Return list of task_ids that `task_id` depends on."""
        stmt = select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == task_id)
        result = await self.session.execute(stmt)
        return [str(row[0]) for row in result.all()]

    async def get_dependencies_for_tasks(self, task_ids: list[str]) -> dict[str, list[str]]:
        """Return {task_id: [depends_on_task_id, ...]} for multiple tasks at once."""
        if not task_ids:
            return {}
        stmt = select(TaskDependency.task_id, TaskDependency.depends_on_task_id).where(
            TaskDependency.task_id.in_(task_ids)
        )
        result = await self.session.execute(stmt)
        out: dict[str, list[str]] = {tid: [] for tid in task_ids}
        for task_id, dep_id in result.all():
            out[str(task_id)].append(str(dep_id))
        return out

    async def set_dependencies(self, task_id: str, depends_on: list[str]) -> None:
        """Replace all dependencies for a task."""
        await self.session.execute(
            delete(TaskDependency).where(TaskDependency.task_id == task_id)
        )
        if depends_on:
            rows = [{"task_id": task_id, "depends_on_task_id": dep_id} for dep_id in depends_on]
            await self.session.execute(insert(TaskDependency), rows)
        await self.session.flush()


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

    async def update_approval(
        self,
        report_id: str,
        is_approved: bool,
        approved_by: "str | None",
        approved_at: object,
    ) -> "TaskReport | None":
        stmt = (
            update(TaskReport)
            .where(TaskReport.id == report_id)
            .values(is_approved=is_approved, approved_by=approved_by, approved_at=approved_at)
            .returning(TaskReport)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()
