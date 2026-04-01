from fastapi import APIRouter
from database import get_db

router = APIRouter()


@router.get("/notifications")
async def list_notifications(limit: int = 20, unread_only: bool = False):
    db = get_db()
    query = db.table("notifications").select("*")
    if unread_only:
        query = query.eq("is_read", False)
    result = query.order("created_at", desc=True).limit(limit).execute()
    return result.data


@router.get("/notifications/unread-count")
async def unread_count():
    db = get_db()
    result = (
        db.table("notifications")
        .select("id", count="exact")
        .eq("is_read", False)
        .execute()
    )
    return {"count": result.count or 0}


@router.put("/notifications/{notification_id}/read")
async def mark_as_read(notification_id: str):
    db = get_db()
    db.table("notifications").update({"is_read": True}).eq("id", notification_id).execute()
    return {"ok": True}


@router.put("/notifications/read-all")
async def mark_all_as_read():
    db = get_db()
    db.table("notifications").update({"is_read": True}).eq("is_read", False).execute()
    return {"ok": True}


@router.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str):
    db = get_db()
    db.table("notifications").delete().eq("id", notification_id).execute()
    return {"ok": True}
