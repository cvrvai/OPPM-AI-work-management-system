"""Notification/audit repository for git service (audit logging only)."""

from repositories.base import BaseRepository
from shared.database import get_db


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
