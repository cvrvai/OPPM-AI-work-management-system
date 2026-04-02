"""Project repository (read-only) for AI service."""

from repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    def __init__(self):
        super().__init__("projects")

    def find_workspace_projects(self, workspace_id: str, limit: int = 500) -> list[dict]:
        q = self._query().select("*").eq("workspace_id", workspace_id)
        q = q.order("created_at", desc=True).range(0, limit - 1)
        return q.execute().data or []
