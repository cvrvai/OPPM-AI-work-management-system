"""
Integration tests for auth router — uses TestClient with mocked dependencies.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from main import create_app
from shared.database import get_session
from shared.auth import get_current_user, CurrentUser


@pytest.fixture
def client():
    app = create_app()
    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = lambda: mock_session
    return TestClient(app, raise_server_exceptions=False)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "auth"


def test_login_missing_fields(client):
    resp = client.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422


def test_me_unauthenticated(client):
    """GET /me without token returns 401."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_authenticated():
    """GET /me with valid JWT override returns user info."""
    app = create_app()
    mock_user = CurrentUser(id="u1", email="user@example.com")
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_session] = lambda: AsyncMock()

    with TestClient(app) as c:
        resp = c.get("/api/v1/auth/me")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "u1"
    assert data["email"] == "user@example.com"
