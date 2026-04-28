"""Notification routes — user-scoped (not workspace-scoped)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import CurrentUser, get_current_user
from shared.database import get_session
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
async def list_notifications_route(
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = False,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await get_notifications(session, user.id, unread_only=unread_only, limit=limit)


@router.get("/unread-count")
async def unread_count_route(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return {"count": await get_unread_count(session, user.id)}


@router.put("/{notification_id}/read")
async def mark_as_read_route(
    notification_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await mark_read(session, notification_id, user.id)
    return SuccessResponse()


@router.put("/read-all")
async def mark_all_as_read_route(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await mark_all_read(session, user.id)
    return SuccessResponse()


@router.delete("/{notification_id}")
async def delete_notification_route(
    notification_id: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SuccessResponse:
    await delete_notification(session, notification_id, user.id)
    return SuccessResponse()
