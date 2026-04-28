"""Test fixtures for workspace service."""

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from main import create_app
from shared.auth import get_current_user, CurrentUser
from shared.database import get_session


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_user():
    return CurrentUser(id="user-1", email="owner@example.com", role="authenticated")


@pytest.fixture
def client(mock_session, mock_user):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return TestClient(app)
