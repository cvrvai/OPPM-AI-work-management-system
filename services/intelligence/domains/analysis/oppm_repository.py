"""OPPM repositories for AI service — needed for chat context building."""

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domains.models.base_repository import BaseRepository
from shared.models.oppm import (
    OPPMObjective, OPPMSubObjective, TaskSubObjective,
    OPPMTimelineEntry, ProjectCost,
    OPPMDeliverable, OPPMForecast, OPPMRisk,
)
from shared.models.task import Task, TaskAssignee, TaskDependency, TaskOwner
from shared.models.workspace import WorkspaceMember


class ObjectiveRepository(BaseRepository):
    model = OPPMObjective

    async def find_with_tasks(self, project_id: str) -> list[dict]:
        stmt = select(OPPMObjective).where(OPPMObjective.project_id == project_id).order_by(OPPMObjective.sort_order)
        result = await self.session.execute(stmt)
        objectives = []
        for obj in result.scalars().all():
            d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            task_stmt = select(Task).where(Task.oppm_objective_id == obj.id).order_by(Task.created_at)
            task_result = await self.session.execute(task_stmt)
            d["tasks"] = [{c.name: getattr(t, c.name) for c in t.__table__.columns} for t in task_result.scalars().all()]
            objectives.append(d)
        return objectives

    async def find_sub_objectives(self, project_id: str) -> list[dict]:
        """Load all 6 sub-objective columns for a project."""
        stmt = (
            select(OPPMSubObjective)
            .where(OPPMSubObjective.project_id == project_id)
            .order_by(OPPMSubObjective.position)
        )
        result = await self.session.execute(stmt)
        return [
            {"id": str(s.id), "position": s.position, "label": s.label}
            for s in result.scalars().all()
        ]

    async def find_task_sub_objective_links(self, project_id: str) -> dict[str, list[str]]:
        """Return {task_id: [sub_objective_id, ...]} for all tasks in a project."""
        stmt = (
            select(TaskSubObjective.task_id, TaskSubObjective.sub_objective_id)
            .join(Task, Task.id == TaskSubObjective.task_id)
            .where(Task.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        mapping: dict[str, list[str]] = {}
        for row in result.all():
            tid = str(row.task_id)
            mapping.setdefault(tid, []).append(str(row.sub_objective_id))
        return mapping


class TimelineRepository(BaseRepository):
    model = OPPMTimelineEntry

    async def find_project_timeline(self, project_id: str) -> list[OPPMTimelineEntry]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="week_start",
            desc=False,
            limit=500,
        )

    async def upsert_entry(self, data: dict) -> OPPMTimelineEntry:
        week_start_val = data["week_start"]
        if isinstance(week_start_val, str):
            week_start_val = date.fromisoformat(week_start_val)

        stmt = (
            select(OPPMTimelineEntry)
            .where(
                OPPMTimelineEntry.project_id == data["project_id"],
                OPPMTimelineEntry.task_id == data["task_id"],
                OPPMTimelineEntry.week_start == week_start_val,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            for k, v in data.items():
                if k == "week_start" and isinstance(v, str):
                    v = date.fromisoformat(v)
                setattr(existing, k, v)
            await self.session.flush()
            return existing

        create_data = {**data, "week_start": week_start_val}
        return await self.create(create_data)


class CostRepository(BaseRepository):
    model = ProjectCost

    async def get_cost_summary(self, project_id: str) -> dict:
        items = await self.find_all(filters={"project_id": project_id}, order_by="created_at")
        total_planned = sum(float(c.planned_amount) for c in items)
        total_actual = sum(float(c.actual_amount) for c in items)
        return {
            "items": items,
            "total_planned": total_planned,
            "total_actual": total_actual,
            "variance": total_planned - total_actual,
        }

    async def get_cost_breakdown(self, project_id: str) -> list[dict]:
        """Per-category cost breakdown (not just totals)."""
        items = await self.find_all(filters={"project_id": project_id}, order_by="created_at")
        return [
            {
                "category": c.category,
                "description": c.description or "",
                "planned": float(c.planned_amount),
                "actual": float(c.actual_amount),
            }
            for c in items
        ]


class DeliverableRepository(BaseRepository):
    model = OPPMDeliverable

    async def find_by_project(self, project_id: str) -> list[dict]:
        items = await self.find_all(
            filters={"project_id": project_id}, order_by="item_number", desc=False,
        )
        return [{"id": str(d.id), "number": d.item_number, "description": d.description} for d in items]


class ForecastRepository(BaseRepository):
    model = OPPMForecast

    async def find_by_project(self, project_id: str) -> list[dict]:
        items = await self.find_all(
            filters={"project_id": project_id}, order_by="item_number", desc=False,
        )
        return [{"id": str(f.id), "number": f.item_number, "description": f.description} for f in items]


class RiskRepository(BaseRepository):
    model = OPPMRisk

    async def find_by_project(self, project_id: str) -> list[dict]:
        items = await self.find_all(
            filters={"project_id": project_id}, order_by="item_number", desc=False,
        )
        return [
            {"id": str(r.id), "number": r.item_number, "description": r.description, "rag": r.rag}
            for r in items
        ]


class TaskDetailRepository(BaseRepository):
    model = Task

    async def find_assignees(self, project_id: str) -> dict[str, list[str]]:
        """Return {task_id: [member_display_name, ...]}."""
        stmt = (
            select(TaskAssignee.task_id, WorkspaceMember.display_name)
            .join(WorkspaceMember, WorkspaceMember.id == TaskAssignee.member_id)
            .join(Task, Task.id == TaskAssignee.task_id)
            .where(Task.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        mapping: dict[str, list[str]] = {}
        for row in result.all():
            tid = str(row.task_id)
            mapping.setdefault(tid, []).append(row.display_name or "unnamed")
        return mapping

    async def find_owners(self, project_id: str) -> dict[str, list[dict]]:
        """Return {task_id: [{name, priority}, ...]}."""
        stmt = (
            select(TaskOwner.task_id, TaskOwner.priority, WorkspaceMember.display_name)
            .join(WorkspaceMember, WorkspaceMember.id == TaskOwner.member_id)
            .join(Task, Task.id == TaskOwner.task_id)
            .where(Task.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        mapping: dict[str, list[dict]] = {}
        for row in result.all():
            tid = str(row.task_id)
            mapping.setdefault(tid, []).append({
                "name": row.display_name or "unnamed",
                "priority": row.priority,
            })
        return mapping

    async def find_dependencies(self, project_id: str) -> dict[str, list[str]]:
        """Return {task_id: [depends_on_task_id, ...]}."""
        stmt = (
            select(TaskDependency.task_id, TaskDependency.depends_on_task_id)
            .join(Task, Task.id == TaskDependency.task_id)
            .where(Task.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        mapping: dict[str, list[str]] = {}
        for row in result.all():
            tid = str(row.task_id)
            mapping.setdefault(tid, []).append(str(row.depends_on_task_id))
        return mapping
