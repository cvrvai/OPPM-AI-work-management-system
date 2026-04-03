"""Notification/audit repository for git service (audit logging only)."""

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.notification import AuditLog


class AuditRepository(BaseRepository):
    model = AuditLog

    async def log(
        self,
        workspace_id: str,
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        old_data: dict | None = None,
        new_data: dict | None = None,
    ) -> AuditLog:
        return await self.create({
            "workspace_id": workspace_id,
            "user_id": user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_data": old_data,
            "new_data": new_data,
        })
