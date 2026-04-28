"""Unit tests for notification_service.py."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_notifications_returns_list():
    from services.notification_service import get_notifications
    session = AsyncMock()
    with patch("services.notification_service.NotificationRepository") as MockRepo:
        MockRepo.return_value.find_user_notifications = AsyncMock(return_value=[])
        result = await get_notifications(session, "user-1")
        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_unread_count_returns_int():
    from services.notification_service import get_unread_count
    session = AsyncMock()
    with patch("services.notification_service.NotificationRepository") as MockRepo:
        MockRepo.return_value.unread_count = AsyncMock(return_value=3)
        result = await get_unread_count(session, "user-1")
        assert result == 3
