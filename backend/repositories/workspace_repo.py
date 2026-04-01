"""Workspace & workspace member repository."""

from repositories.base import BaseRepository
from database import get_db


class WorkspaceRepository(BaseRepository):
    def __init__(self):
        super().__init__("workspaces")

    def find_by_slug(self, slug: str) -> dict | None:
        result = self._query().select("*").eq("slug", slug).limit(1).execute()
        return result.data[0] if result.data else None

    def find_user_workspaces(self, user_id: str) -> list[dict]:
        db = get_db()
        memberships = (
            db.table("workspace_members")
            .select("workspace_id, role")
            .eq("user_id", user_id)
            .execute()
        )
        if not memberships.data:
            return []
        ws_ids = [m["workspace_id"] for m in memberships.data]
        result = self._query().select("*").in_("id", ws_ids).order("name").execute()
        # Attach role to each workspace
        role_map = {m["workspace_id"]: m["role"] for m in memberships.data}
        for ws in result.data or []:
            ws["current_user_role"] = role_map.get(ws["id"], "member")
        return result.data or []


class WorkspaceMemberRepository(BaseRepository):
    def __init__(self):
        super().__init__("workspace_members")

    def find_by_user_and_workspace(self, user_id: str, workspace_id: str) -> dict | None:
        result = (
            self._query()
            .select("*")
            .eq("workspace_id", workspace_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def find_members(self, workspace_id: str) -> list[dict]:
        return self.find_all(filters={"workspace_id": workspace_id}, order_by="joined_at", desc=False)


class WorkspaceInviteRepository(BaseRepository):
    def __init__(self):
        super().__init__("workspace_invites")

    def find_by_token(self, token: str) -> dict | None:
        result = self._query().select("*").eq("token", token).limit(1).execute()
        return result.data[0] if result.data else None

    def find_pending(self, workspace_id: str) -> list[dict]:
        return (
            self._query()
            .select("*")
            .eq("workspace_id", workspace_id)
            .is_("accepted_at", "null")
            .order("created_at", desc=True)
            .execute()
        ).data or []
