"""Project & project member repository."""

from repositories.base import BaseRepository
from database import get_db


class ProjectRepository(BaseRepository):
    def __init__(self):
        super().__init__("projects")

    def find_workspace_projects(
        self,
        workspace_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        q = self._query().select("*").eq("workspace_id", workspace_id)
        if status:
            q = q.eq("status", status)
        q = q.order("created_at", desc=True)
        if limit:
            q = q.range(offset, offset + limit - 1)
        return q.execute().data or []

    def update_progress(self, project_id: str, progress: int) -> None:
        self._query().update({"progress": progress}).eq("id", project_id).execute()


class ProjectMemberRepository(BaseRepository):
    def __init__(self):
        super().__init__("project_members")

    def find_project_members(self, project_id: str) -> list[dict]:
        db = get_db()
        result = (
            db.table("project_members")
            .select("*, workspace_members(id, display_name, avatar_url, user_id, role)")
            .eq("project_id", project_id)
            .order("joined_at")
            .execute()
        )
        return result.data or []

    def add_member(self, project_id: str, member_id: str, role: str = "contributor") -> dict:
        return self.create({
            "project_id": project_id,
            "member_id": member_id,
            "role": role,
        })

    def remove_member(self, project_id: str, member_id: str) -> bool:
        self.db.table("project_members").delete().eq("project_id", project_id).eq("member_id", member_id).execute()
        return True
