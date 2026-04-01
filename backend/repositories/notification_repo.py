"""Notification & audit log repositories."""

from repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    def __init__(self):
        super().__init__("notifications")

    def find_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        q = self._query().select("*").eq("user_id", user_id)
        if unread_only:
            q = q.eq("is_read", False)
        result = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        return result.data or []

    def unread_count(self, user_id: str) -> int:
        result = (
            self._query()
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .execute()
        )
        return result.count or 0

    def mark_read(self, notification_id: str) -> None:
        self._query().update({"is_read": True}).eq("id", notification_id).execute()

    def mark_all_read(self, user_id: str) -> None:
        self._query().update({"is_read": True}).eq("user_id", user_id).eq("is_read", False).execute()


class AuditRepository(BaseRepository):
    def __init__(self):
        super().__init__("audit_log")

    def log(
        self,
        workspace_id: str,
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        old_data: dict | None = None,
        new_data: dict | None = None,
    ) -> dict:
        return self.create({
            "workspace_id": workspace_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_data": old_data,
            "new_data": new_data,
        })
