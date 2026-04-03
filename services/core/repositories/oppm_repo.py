"""OPPM objectives, timeline, and costs repositories."""

from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.oppm import OPPMObjective, OPPMTimelineEntry, ProjectCost
from shared.models.task import Task


class ObjectiveRepository(BaseRepository):
    model = OPPMObjective

    async def find_project_objectives(self, project_id: str) -> list[OPPMObjective]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="sort_order",
            desc=False,
        )

    async def find_with_tasks(self, project_id: str) -> list[dict]:
        """Get objectives with nested tasks for OPPM view."""
        objectives = await self.find_project_objectives(project_id)
        result = []
        for obj in objectives:
            d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            stmt = select(Task).where(Task.oppm_objective_id == obj.id).order_by(Task.created_at)
            tasks_result = await self.session.execute(stmt)
            d["tasks"] = [{c.name: getattr(t, c.name) for c in t.__table__.columns} for t in tasks_result.scalars().all()]
            result.append(d)
        return result


class TimelineRepository(BaseRepository):
    model = OPPMTimelineEntry

    async def find_project_timeline(self, project_id: str) -> list[OPPMTimelineEntry]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="week_start",
            desc=False,
        )

    async def upsert_entry(self, data: dict) -> OPPMTimelineEntry:
        """Insert or update a timeline entry by (objective_id, week_start)."""
        # Convert week_start string to date object for type-safe DB comparison
        week_start_val = data["week_start"]
        if isinstance(week_start_val, str):
            week_start_val = date.fromisoformat(week_start_val)
        stmt = (
            select(OPPMTimelineEntry)
            .where(
                OPPMTimelineEntry.objective_id == data["objective_id"],
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
        # Ensure week_start is a date in the create dict too
        create_data = {**data, "week_start": week_start_val}
        return await self.create(create_data)


class CostRepository(BaseRepository):
    model = ProjectCost

    async def find_project_costs(self, project_id: str) -> list[ProjectCost]:
        return await self.find_all(
            filters={"project_id": project_id},
            order_by="created_at",
            desc=False,
        )

    async def get_cost_summary(self, project_id: str) -> dict:
        costs = await self.find_project_costs(project_id)
        return {
            "total_planned": sum(float(c.planned_amount) for c in costs),
            "total_actual": sum(float(c.actual_amount) for c in costs),
            "items": costs,
        }
