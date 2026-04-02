"""OPPM objectives, timeline, and costs repositories."""

from repositories.base import BaseRepository
from shared.database import get_db


class ObjectiveRepository(BaseRepository):
    def __init__(self):
        super().__init__("oppm_objectives")

    def find_project_objectives(self, project_id: str) -> list[dict]:
        return self.find_all(
            filters={"project_id": project_id},
            order_by="sort_order",
            desc=False,
        )

    def find_with_tasks(self, project_id: str) -> list[dict]:
        """Get objectives with nested tasks for OPPM view."""
        db = get_db()
        objectives = self.find_project_objectives(project_id)
        for obj in objectives:
            tasks = (
                db.table("tasks")
                .select("*")
                .eq("oppm_objective_id", obj["id"])
                .order("created_at")
                .execute()
            )
            obj["tasks"] = tasks.data or []
        return objectives


class TimelineRepository(BaseRepository):
    def __init__(self):
        super().__init__("oppm_timeline_entries")

    def find_project_timeline(self, project_id: str) -> list[dict]:
        return self.find_all(
            filters={"project_id": project_id},
            order_by="week_start",
            desc=False,
        )

    def upsert_entry(self, data: dict) -> dict:
        """Insert or update a timeline entry by (objective_id, week_start)."""
        existing = (
            self._query()
            .select("id")
            .eq("objective_id", data["objective_id"])
            .eq("week_start", data["week_start"])
            .limit(1)
            .execute()
        )
        if existing.data:
            return self.update(existing.data[0]["id"], data)
        return self.create(data)


class CostRepository(BaseRepository):
    def __init__(self):
        super().__init__("project_costs")

    def find_project_costs(self, project_id: str) -> list[dict]:
        return self.find_all(
            filters={"project_id": project_id},
            order_by="created_at",
            desc=False,
        )

    def get_cost_summary(self, project_id: str) -> dict:
        costs = self.find_project_costs(project_id)
        return {
            "total_planned": sum(float(c.get("planned_amount", 0)) for c in costs),
            "total_actual": sum(float(c.get("actual_amount", 0)) for c in costs),
            "items": costs,
        }
