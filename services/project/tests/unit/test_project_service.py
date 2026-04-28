"""Unit tests for project_service.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_get_project_not_found():
    from services.project_service import get_project
    session = AsyncMock()
    with patch("services.project_service.ProjectRepository") as MockRepo:
        MockRepo.return_value.find_by_id = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc_info:
            await get_project(session, "proj-1", "ws-1")
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_project_wrong_workspace():
    from services.project_service import get_project
    session = AsyncMock()
    with patch("services.project_service.ProjectRepository") as MockRepo:
        mock_proj = MagicMock()
        mock_proj.workspace_id = "ws-OTHER"
        MockRepo.return_value.find_by_id = AsyncMock(return_value=mock_proj)
        with pytest.raises(HTTPException) as exc_info:
            await get_project(session, "proj-1", "ws-1")
        assert exc_info.value.status_code == 404
