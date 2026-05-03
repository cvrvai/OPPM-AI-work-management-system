"""OPPM repositories for AI service — needed for chat context building."""

from datetime import date, datetime

from sqlalchemy import select, update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from domains.models.base_repository import BaseRepository
from shared.models.oppm import (
    OPPMObjective, OPPMSubObjective, TaskSubObjective,
    OPPMTimelineEntry, ProjectCost,
    OPPMDeliverable, OPPMForecast, OPPMRisk,
    OPPMHeader, OPPMBorderOverride,
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


class HeaderRepository(BaseRepository):
    model = OPPMHeader

    async def find_by_project(self, project_id: str) -> OPPMHeader | None:
        stmt = select(OPPMHeader).where(OPPMHeader.project_id == project_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(self, project_id: str, workspace_id: str, data: dict) -> OPPMHeader:
        existing = await self.find_by_project(project_id)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            return existing
        return await self.create({"project_id": project_id, "workspace_id": workspace_id, **data})


class SubObjectiveRepository(BaseRepository):
    model = OPPMSubObjective

    async def upsert_at_position(self, project_id: str, position: int, label: str) -> OPPMSubObjective:
        if not 1 <= position <= 6:
            raise ValueError(f"position must be 1-6, got {position}")
        stmt = (
            select(OPPMSubObjective)
            .where(OPPMSubObjective.project_id == project_id, OPPMSubObjective.position == position)
            .limit(1)
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.label = label
            await self.session.flush()
            return existing
        return await self.create({"project_id": project_id, "position": position, "label": label})

    async def delete_at_position(self, project_id: str, position: int) -> bool:
        await self.session.execute(
            sa_delete(OPPMSubObjective).where(
                OPPMSubObjective.project_id == project_id,
                OPPMSubObjective.position == position,
            )
        )
        await self.session.flush()
        return True


class TaskSubObjectiveLinkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def set_links(self, task_id: str, sub_objective_ids: list[str]) -> list[str]:
        await self.session.execute(
            sa_delete(TaskSubObjective).where(TaskSubObjective.task_id == task_id)
        )
        for so_id in sub_objective_ids:
            self.session.add(TaskSubObjective(task_id=task_id, sub_objective_id=so_id))
        await self.session.flush()
        return sub_objective_ids


class TaskOwnerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def set_owner(self, task_id: str, member_id: str, priority: str) -> dict:
        if priority not in ("A", "B", "C"):
            raise ValueError(f"priority must be A/B/C, got {priority!r}")
        stmt = (
            select(TaskOwner)
            .where(TaskOwner.task_id == task_id, TaskOwner.member_id == member_id)
            .limit(1)
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.priority = priority
            await self.session.flush()
            return {"task_id": str(task_id), "member_id": str(member_id), "priority": priority}
        owner = TaskOwner(task_id=task_id, member_id=member_id, priority=priority)
        self.session.add(owner)
        await self.session.flush()
        return {"task_id": str(task_id), "member_id": str(member_id), "priority": priority}

    async def remove_owner(self, task_id: str, member_id: str) -> bool:
        await self.session.execute(
            sa_delete(TaskOwner).where(
                TaskOwner.task_id == task_id, TaskOwner.member_id == member_id
            )
        )
        await self.session.flush()
        return True


class _NumberedItemMixin:
    """Shared upsert/delete logic for OPPMRisk / OPPMForecast / OPPMDeliverable
    which all use (project_id, item_number) as their natural key."""

    model = None  # set by subclass

    async def upsert(self, project_id: str, item_number: int, fields: dict):
        stmt = (
            select(self.model)
            .where(self.model.project_id == project_id, self.model.item_number == item_number)
            .limit(1)
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            await self.session.flush()
            return existing
        instance = self.model(project_id=project_id, item_number=item_number, **fields)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete_by_number(self, project_id: str, item_number: int) -> bool:
        await self.session.execute(
            sa_delete(self.model).where(
                self.model.project_id == project_id,
                self.model.item_number == item_number,
            )
        )
        await self.session.flush()
        return True


class RiskWriteRepository(_NumberedItemMixin, BaseRepository):
    model = OPPMRisk


class ForecastWriteRepository(_NumberedItemMixin, BaseRepository):
    model = OPPMForecast


class DeliverableWriteRepository(_NumberedItemMixin, BaseRepository):
    model = OPPMDeliverable


class BorderOverrideRepository:
    """Repository for FortuneSheet cell border overrides.

    Stores AI/user edits as a delta layer on top of the generated scaffold.
    Each row = one cell side (top/bottom/left/right).
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_project(self, project_id: str) -> list[OPPMBorderOverride]:
        stmt = (
            select(OPPMBorderOverride)
            .where(OPPMBorderOverride.project_id == project_id)
            .order_by(OPPMBorderOverride.cell_row, OPPMBorderOverride.cell_col)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        project_id: str,
        workspace_id: str,
        cell_row: int,
        cell_col: int,
        side: str,
        style: str,
        color: str,
        created_by: str | None = None,
    ) -> OPPMBorderOverride:
        stmt = (
            select(OPPMBorderOverride)
            .where(
                OPPMBorderOverride.project_id == project_id,
                OPPMBorderOverride.cell_row == cell_row,
                OPPMBorderOverride.cell_col == cell_col,
                OPPMBorderOverride.side == side,
            )
            .limit(1)
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.style = style
            existing.color = color
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            return existing
        instance = OPPMBorderOverride(
            project_id=project_id,
            workspace_id=workspace_id,
            cell_row=cell_row,
            cell_col=cell_col,
            side=side,
            style=style,
            color=color,
            created_by=created_by,
        )
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete_by_project(self, project_id: str) -> int:
        result = await self.session.execute(
            sa_delete(OPPMBorderOverride).where(OPPMBorderOverride.project_id == project_id)
        )
        await self.session.flush()
        return result.rowcount or 0


class CostWriteRepository(BaseRepository):
    """ProjectCost has no natural key beyond (project_id, category, period); upsert by category+period."""

    model = ProjectCost

    async def upsert_by_category(
        self,
        project_id: str,
        category: str,
        period: str | None,
        fields: dict,
    ) -> ProjectCost:
        stmt = select(ProjectCost).where(
            ProjectCost.project_id == project_id,
            ProjectCost.category == category,
        )
        if period is not None:
            stmt = stmt.where(ProjectCost.period == period)
        existing = (await self.session.execute(stmt.limit(1))).scalar_one_or_none()
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.updated_at = datetime.utcnow()
            await self.session.flush()
            return existing
        return await self.create({
            "project_id": project_id,
            "category": category,
            "period": period,
            **fields,
        })
