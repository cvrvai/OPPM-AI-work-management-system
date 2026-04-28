"""
Unit tests for workspace_service.py — business logic with mocked repos.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_create_workspace_slug_conflict():
    """create_workspace() raises 409 when slug already exists."""
    from services.workspace_service import create_workspace

    session = AsyncMock()
    with patch("services.workspace_service.WorkspaceRepository") as MockRepo:
        instance = MockRepo.return_value
        instance.find_by_slug = AsyncMock(return_value=MagicMock())  # slug exists

        with pytest.raises(HTTPException) as exc_info:
            await create_workspace(session, "user-1", "My Workspace", "my-workspace")

        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_get_workspace_not_member():
    """get_workspace() raises 403 when user is not a workspace member."""
    from services.workspace_service import get_workspace

    session = AsyncMock()
    with patch("services.workspace_service.WorkspaceRepository") as MockWsRepo, \
         patch("services.workspace_service.WorkspaceMemberRepository") as MockMemRepo:
        MockWsRepo.return_value.find_by_id = AsyncMock(return_value=MagicMock())
        MockMemRepo.return_value.find_by_user_and_workspace = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_workspace(session, "ws-id", "user-id")

        assert exc_info.value.status_code == 403
