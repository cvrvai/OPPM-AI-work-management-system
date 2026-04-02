"""Project repository (read-only) for git service — needed for workspace project lookups."""

from repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    def __init__(self):
        super().__init__("projects")

    def find_workspace_projects(self, workspace_id: str, status: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
        q = self._query().select("*").eq("workspace_id", workspace_id)
        if status:
            q = q.eq("status", status)
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        return q.execute().data or []
