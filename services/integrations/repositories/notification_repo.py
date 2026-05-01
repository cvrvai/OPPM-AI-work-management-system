"""Minimal audit repository for integrations service."""

from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.notification import AuditLog


class AuditRepository:
    """Minimal audit repo — only what integrations needs."""

    def __init__(self, session: AsyncSession):
        self.session = session

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
        log = AuditLog(
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_data=old_data,
            new_data=new_data,
        )
        self.session.add(log)
        await self.session.flush()
        return log
