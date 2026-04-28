"""Notification repository — migrated from services/core."""

from sqlalchemy import select, update, delete, func

from repositories.base import BaseRepository
from shared.models.notification import Notification


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
            stmt = stmt.where(Notification.is_read == False)  # noqa: E712
        stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def unread_count(self, user_id: str) -> int:
        stmt = (
            select(func.count(Notification.id))
            .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

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
            .where(Notification.user_id == user_id, Notification.is_read == False)  # noqa: E712
            .values(is_read=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def delete_for_user(self, notification_id: str, user_id: str) -> None:
        stmt = delete(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
        await self.session.execute(stmt)
        await self.session.flush()
