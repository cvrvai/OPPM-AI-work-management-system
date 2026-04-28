"""Notification service — migrated from services/core/services/notification_service.py."""

from sqlalchemy.ext.asyncio import AsyncSession
from repositories.notification_repo import NotificationRepository


async def get_notifications(
    session: AsyncSession, user_id: str, unread_only: bool = False, limit: int = 20
) -> list[dict]:
    repo = NotificationRepository(session)
    return await repo.find_user_notifications(user_id, unread_only=unread_only, limit=limit)


async def get_unread_count(session: AsyncSession, user_id: str) -> int:
    repo = NotificationRepository(session)
    return await repo.unread_count(user_id)


async def mark_read(session: AsyncSession, notification_id: str, user_id: str) -> None:
    repo = NotificationRepository(session)
    await repo.mark_read_for_user(notification_id, user_id)


async def mark_all_read(session: AsyncSession, user_id: str) -> None:
    repo = NotificationRepository(session)
    await repo.mark_all_read(user_id)


async def delete_notification(session: AsyncSession, notification_id: str, user_id: str) -> None:
    repo = NotificationRepository(session)
    await repo.delete_for_user(notification_id, user_id)


async def create_notification(
    session: AsyncSession,
    user_id: str | None,
    workspace_id: str | None,
    notification_type: str,
    title: str,
    message: str = "",
    link: str | None = None,
    metadata: dict | None = None,
) -> dict:
    repo = NotificationRepository(session)
    return await repo.create({
        "user_id": user_id,
        "workspace_id": workspace_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "link": link,
        "metadata": metadata or {},
    })
