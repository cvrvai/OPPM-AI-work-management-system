"""
Notification service.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from domains.notification.repository import NotificationRepository


async def get_notifications(session: AsyncSession, user_id: str, unread_only: bool = False, limit: int = 20) -> list[dict]:
    notification_repo = NotificationRepository(session)
    return await notification_repo.find_user_notifications(user_id, unread_only=unread_only, limit=limit)


async def get_unread_count(session: AsyncSession, user_id: str) -> int:
    notification_repo = NotificationRepository(session)
    return await notification_repo.unread_count(user_id)


async def mark_read(session: AsyncSession, notification_id: str, user_id: str) -> dict:
    notification_repo = NotificationRepository(session)
    await notification_repo.mark_read_for_user(notification_id, user_id)
    return {"ok": True}


async def mark_all_read(session: AsyncSession, user_id: str) -> dict:
    notification_repo = NotificationRepository(session)
    await notification_repo.mark_all_read(user_id)
    return {"ok": True}


async def delete_notification(session: AsyncSession, notification_id: str, user_id: str) -> bool:
    notification_repo = NotificationRepository(session)
    return await notification_repo.delete_for_user(notification_id, user_id)


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
    notification_repo = NotificationRepository(session)
    return await notification_repo.create({
        "user_id": user_id,
        "workspace_id": workspace_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "link": link,
        "metadata": metadata or {},
    })
