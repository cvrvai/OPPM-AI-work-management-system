"""Test fixtures for project service."""

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from main import create_app
from shared.auth import get_current_user, get_workspace_context, CurrentUser, WorkspaceContext
from shared.database import get_session


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_user():
    return CurrentUser(id="user-1", email="user@example.com")


@pytest.fixture
def mock_ws():
    return WorkspaceContext(
        workspace_id="ws-1",
        user=CurrentUser(id="user-1", email="user@example.com"),
        member_id="mem-1",
        role="member",
    )


@pytest.fixture
def client(mock_session, mock_ws):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: mock_session
    app.dependency_overrides[get_workspace_context] = lambda: mock_ws
    return TestClient(app, raise_server_exceptions=False)
