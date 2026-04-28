"""Audit repository for project service."""

import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.notification import AuditLog

logger = logging.getLogger(__name__)


class AuditRepository(BaseRepository):
    model = AuditLog

    async def log(
        self,
        workspace_id: str,
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        old_data: dict[str, Any] | None = None,
        new_data: dict[str, Any] | None = None,
    ) -> None:
        try:
            await self.create({
                "workspace_id": workspace_id,
                "user_id": user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "old_data": old_data,
                "new_data": new_data,
            })
        except Exception as exc:
            logger.warning("audit log failed: %s", exc)
