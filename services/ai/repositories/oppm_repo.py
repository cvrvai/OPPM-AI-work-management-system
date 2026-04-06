"""OPPM repositories for AI service — needed for chat context building."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.oppm import OPPMObjective, OPPMTimelineEntry, ProjectCost
from shared.models.task import Task


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
        stmt = (
            select(OPPMTimelineEntry)
            .where(
                OPPMTimelineEntry.project_id == data["project_id"],
                OPPMTimelineEntry.task_id == data["task_id"],
                OPPMTimelineEntry.week_start == data["week_start"],
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            await self.session.flush()
            return existing
        return await self.create(data)


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
