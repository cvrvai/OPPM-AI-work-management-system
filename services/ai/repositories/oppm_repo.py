"""OPPM repositories for AI service — needed for chat context building."""

from repositories.base import BaseRepository
from shared.database import get_db


class ObjectiveRepository(BaseRepository):
    def __init__(self):
        super().__init__("oppm_objectives")

    def find_with_tasks(self, project_id: str) -> list[dict]:
        db = get_db()
        result = (
            db.table("oppm_objectives")
            .select("*, tasks(*)")
            .eq("project_id", project_id)
            .order("sort_order")
            .execute()
        )
        return result.data or []


class TimelineRepository(BaseRepository):
    def __init__(self):
        super().__init__("oppm_timeline_entries")

    def find_project_timeline(self, project_id: str) -> list[dict]:
        return self.find_all(
            filters={"project_id": project_id},
            order_by="week_start",
            desc=False,
            limit=500,
        )

    def upsert_entry(self, data: dict) -> dict:
        db = get_db()
        existing = (
            db.table("oppm_timeline_entries")
            .select("id")
            .eq("project_id", data["project_id"])
            .eq("objective_id", data["objective_id"])
            .eq("week_start", data["week_start"])
            .limit(1)
            .execute()
        )
        if existing.data:
            result = db.table("oppm_timeline_entries").update(data).eq("id", existing.data[0]["id"]).execute()
        else:
            result = db.table("oppm_timeline_entries").insert(data).execute()
        return result.data[0]


class CostRepository(BaseRepository):
    def __init__(self):
        super().__init__("project_costs")

    def get_cost_summary(self, project_id: str) -> dict:
        items = self.find_all(filters={"project_id": project_id}, order_by="created_at")
        total_planned = sum(c.get("planned_amount", 0) for c in items)
        total_actual = sum(c.get("actual_amount", 0) for c in items)
        return {
            "items": items,
            "total_planned": total_planned,
            "total_actual": total_actual,
            "variance": total_planned - total_actual,
        }
