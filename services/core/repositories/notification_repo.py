"""Notification & audit log repositories."""

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.base import BaseRepository
from shared.models.notification import Notification, AuditLog


class NotificationRepository(BaseRepository):
    model = Notification

    async def find_user_notifications(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.is_read == False)
        stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def unread_count(self, user_id: str) -> int:
        stmt = (
            select(func.count(Notification.id))
            .where(Notification.user_id == user_id, Notification.is_read == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def mark_read(self, notification_id: str) -> None:
        stmt = update(Notification).where(Notification.id == notification_id).values(is_read=True)
        await self.session.execute(stmt)
        await self.session.flush()

    async def mark_read_for_user(self, notification_id: str, user_id: str) -> None:
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(is_read=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def mark_all_read(self, user_id: str) -> None:
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read == False)
            .values(is_read=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def delete_for_user(self, notification_id: str, user_id: str) -> bool:
        stmt = delete(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return True


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



