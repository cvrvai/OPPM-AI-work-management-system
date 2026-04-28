"""Unit tests for task_service.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_get_task_not_found():
    from services.task_service import get_task
    session = AsyncMock()
    with patch("services.task_service.TaskRepository") as MockRepo:
        MockRepo.return_value.find_by_id = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc_info:
            await get_task(session, "task-1", "ws-1")
        assert exc_info.value.status_code == 404
