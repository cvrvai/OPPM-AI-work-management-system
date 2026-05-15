"""Task repository."""

from sqlalchemy import select, delete, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.workspace.base_repository import BaseRepository
from shared.models.oppm import OPPMProjectAllMember, OPPMVirtualMember
from shared.models.task import Task, TaskReport, TaskDependency, TaskVirtualAssignee, TaskOwner
from shared.models.project import Project
from shared.models.user import User
from shared.models.workspace import WorkspaceMember


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

    # ── Virtual assignees ──────────────────────────────────────────────

    async def get_virtual_assignees(self, task_id: str) -> list[dict]:
        """Return list of virtual member dicts assigned to a task."""
        stmt = (
            select(
                TaskVirtualAssignee.id,
                TaskVirtualAssignee.assigned_at,
                TaskVirtualAssignee.virtual_member_id,
            )
            .where(TaskVirtualAssignee.task_id == task_id)
        )
        result = await self.session.execute(stmt)
        return [
            {
                "id": str(row.id),
                "virtual_member_id": str(row.virtual_member_id),
                "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
            }
            for row in result.all()
        ]

    async def set_virtual_assignees(self, task_id: str, virtual_member_ids: list[str]) -> None:
        """Replace all virtual assignees for a task."""
        await self.session.execute(
            delete(TaskVirtualAssignee).where(TaskVirtualAssignee.task_id == task_id)
        )
        if virtual_member_ids:
            rows = [{"task_id": task_id, "virtual_member_id": vm_id} for vm_id in virtual_member_ids]
            await self.session.execute(insert(TaskVirtualAssignee), rows)
        await self.session.flush()

    async def get_virtual_assignees_for_tasks(self, task_ids: list[str]) -> dict[str, list[dict]]:
        """Return {task_id: [virtual_assignee_dict, ...]} for multiple tasks."""
        if not task_ids:
            return {}
        stmt = (
            select(
                TaskVirtualAssignee.task_id,
                TaskVirtualAssignee.id,
                TaskVirtualAssignee.assigned_at,
                TaskVirtualAssignee.virtual_member_id,
            )
            .where(TaskVirtualAssignee.task_id.in_(task_ids))
        )
        result = await self.session.execute(stmt)
        out: dict[str, list[dict]] = {tid: [] for tid in task_ids}
        for row in result.all():
            out[str(row.task_id)].append({
                "id": str(row.id),
                "virtual_member_id": str(row.virtual_member_id),
                "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
            })
        return out

    # ── OPPM owners ───────────────────────────────────────────────────────

    async def get_owners(self, task_id: str) -> list[dict]:
        """Return ordered A/B/C owner records for a task."""
        owners_by_task = await self.get_owners_for_tasks([task_id])
        return owners_by_task.get(task_id, [])

    async def set_owners(self, task_id: str, owners: list[dict]) -> None:
        """Replace all A/B/C owners for a task.

        Each owner dict must have `member_id` (referring to
        oppm_project_all_members.id) and `priority` ('A'|'B'|'C').
        """
        await self.session.execute(
            delete(TaskOwner).where(TaskOwner.task_id == task_id)
        )
        if owners:
            rows = [
                {"task_id": task_id, "member_id": o["member_id"], "priority": o["priority"]}
                for o in owners
            ]
            await self.session.execute(insert(TaskOwner), rows)
        await self.session.flush()

    async def get_owners_for_tasks(self, task_ids: list[str]) -> dict[str, list[dict]]:
        """Return {task_id: [owner_dict, ...]} for multiple tasks."""
        if not task_ids:
            return {}
        stmt = (
            select(
                TaskOwner.task_id,
                TaskOwner.member_id,
                TaskOwner.priority,
                OPPMProjectAllMember.workspace_member_id,
                OPPMProjectAllMember.virtual_member_id,
                WorkspaceMember.display_name,
                User.full_name,
                User.email,
                OPPMVirtualMember.name.label('virtual_name'),
            )
            .join(OPPMProjectAllMember, OPPMProjectAllMember.id == TaskOwner.member_id)
            .outerjoin(WorkspaceMember, WorkspaceMember.id == OPPMProjectAllMember.workspace_member_id)
            .outerjoin(User, User.id == WorkspaceMember.user_id)
            .outerjoin(OPPMVirtualMember, OPPMVirtualMember.id == OPPMProjectAllMember.virtual_member_id)
            .where(TaskOwner.task_id.in_(task_ids))
        )
        result = await self.session.execute(stmt)
        out: dict[str, list[dict]] = {tid: [] for tid in task_ids}
        priority_order = {"A": 0, "B": 1, "C": 2}
        for row in result.all():
            email = row.email or ""
            fallback_name = email.split("@")[0] if email else None
            out[str(row.task_id)].append({
                "member_id": str(row.member_id),
                "workspace_member_id": str(row.workspace_member_id) if row.workspace_member_id else None,
                "display_name": row.display_name or row.full_name or fallback_name or row.virtual_name,
                "priority": row.priority,
            })
        for owners in out.values():
            owners.sort(key=lambda owner: priority_order.get(str(owner.get("priority") or "").upper(), 99))
        return out


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
