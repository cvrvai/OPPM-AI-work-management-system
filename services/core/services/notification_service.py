"""
Notification service.
"""

from repositories.notification_repo import NotificationRepository

notification_repo = NotificationRepository()


def get_notifications(user_id: str, unread_only: bool = False, limit: int = 20) -> list[dict]:
    return notification_repo.find_user_notifications(user_id, unread_only=unread_only, limit=limit)


def get_unread_count(user_id: str) -> int:
    return notification_repo.unread_count(user_id)


def mark_read(notification_id: str, user_id: str) -> dict:
    notification_repo.mark_read_for_user(notification_id, user_id)
    return {"ok": True}


def mark_all_read(user_id: str) -> dict:
    notification_repo.mark_all_read(user_id)
    return {"ok": True}


def delete_notification(notification_id: str, user_id: str) -> bool:
    return notification_repo.delete_for_user(notification_id, user_id)


def create_notification(
    user_id: str | None,
    workspace_id: str | None,
    notification_type: str,
    title: str,
    message: str = "",
    link: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return notification_repo.create({
        "user_id": user_id,
        "workspace_id": workspace_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "link": link,
        "metadata": metadata or {},
    })
