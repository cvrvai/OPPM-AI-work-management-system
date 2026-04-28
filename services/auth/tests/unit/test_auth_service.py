"""
Unit tests for auth_service.py — business logic with mocked DB.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_register_conflict():
    """register() raises AuthConflictError when email already exists."""
    from services.auth_service import register
    from exceptions.auth_errors import AuthConflictError

    session = AsyncMock(spec=AsyncSession)
    # Simulate existing user found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = MagicMock()
    session.execute.return_value = mock_result

    with pytest.raises(AuthConflictError):
        await register(session, "exists@example.com", "password123")


@pytest.mark.asyncio
async def test_register_success():
    """register() returns token dict when email is new."""
    from services.auth_service import register

    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    with patch("services.auth_service._create_access_token", return_value="access-tok"), \
         patch("services.auth_service._create_refresh_token", return_value="refresh-tok"):
        result = await register(session, "new@example.com", "password123", "Test User")

    assert result["access_token"] == "access-tok"
    assert result["refresh_token"] == "refresh-tok"
    assert result["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_update_profile_not_found():
    """update_profile() raises AuthNotFoundError when user does not exist."""
    from services.auth_service import update_profile
    from exceptions.auth_errors import AuthNotFoundError

    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    with pytest.raises(AuthNotFoundError):
        await update_profile(session, "nonexistent-id", {"full_name": "New Name"})
