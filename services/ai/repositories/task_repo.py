"""Task repository (read-only) for AI service — used for commit analysis context."""

from repositories.base import BaseRepository


class TaskRepository(BaseRepository):
    def __init__(self):
        super().__init__("tasks")

    def find_project_tasks(self, project_id: str, limit: int = 500) -> list[dict]:
        q = self._query().select("*").eq("project_id", project_id)
        q = q.order("created_at", desc=True).range(0, limit - 1)
        return q.execute().data or []
