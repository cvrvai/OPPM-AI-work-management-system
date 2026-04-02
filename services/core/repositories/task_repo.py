"""Task repository."""

from repositories.base import BaseRepository


class TaskRepository(BaseRepository):
    def __init__(self):
        super().__init__("tasks")

    def find_workspace_tasks(
        self,
        workspace_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        q = self._query().select("*").eq("workspace_id", workspace_id)
        if status:
            q = q.eq("status", status)
        q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
        return q.execute().data or []

    def find_project_tasks(
        self,
        project_id: str,
        status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict]:
        q = self._query().select("*").eq("project_id", project_id)
        if status:
            q = q.eq("status", status)
        q = q.order("created_at", desc=True)
        if limit:
            q = q.range(offset, offset + limit - 1)
        return q.execute().data or []

    def find_by_objective(self, objective_id: str) -> list[dict]:
        return self.find_all(
            filters={"oppm_objective_id": objective_id},
            order_by="created_at",
            desc=False,
        )

    def get_project_progress_data(self, project_id: str) -> list[dict]:
        """Get progress + contribution for all tasks in a project (for weighted calc)."""
        result = (
            self._query()
            .select("progress, project_contribution")
            .eq("project_id", project_id)
            .execute()
        )
        return result.data or []
