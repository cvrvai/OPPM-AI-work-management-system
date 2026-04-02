"""Notification routes — user-scoped (not workspace-scoped)."""

from fastapi import APIRouter, Depends, Query
from shared.auth import CurrentUser, get_current_user
from shared.schemas.common import SuccessResponse
from services.notification_service import (
    get_notifications,
    get_unread_count,
    mark_read,
    mark_all_read,
    delete_notification,
)

router = APIRouter(prefix="/notifications")


@router.get("")
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    user: CurrentUser = Depends(get_current_user),
):
    return get_notifications(user.id, unread_only=unread_only, limit=limit)


@router.get("/unread-count")
async def unread_count(user: CurrentUser = Depends(get_current_user)):
    return {"count": get_unread_count(user.id)}


@router.put("/{notification_id}/read")
async def mark_as_read(notification_id: str, user: CurrentUser = Depends(get_current_user)) -> SuccessResponse:
    mark_read(notification_id, user.id)
    return SuccessResponse()


@router.put("/read-all")
async def mark_all_as_read_route(user: CurrentUser = Depends(get_current_user)) -> SuccessResponse:
    mark_all_read(user.id)
    return SuccessResponse()


@router.delete("/{notification_id}")
async def delete_notification_route(notification_id: str, user: CurrentUser = Depends(get_current_user)) -> SuccessResponse:
    delete_notification(notification_id, user.id)
    return SuccessResponse()
