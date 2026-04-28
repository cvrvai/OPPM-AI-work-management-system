"""Integration tests for notification router."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from main import create_app
from shared.database import get_session
from shared.auth import get_current_user, CurrentUser


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_session] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="u1", email="u@test.com")
    return TestClient(app, raise_server_exceptions=False)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "notification"


def test_notifications_unauthenticated():
    app = create_app()
    app.dependency_overrides[get_session] = lambda: AsyncMock()
    c = TestClient(app, raise_server_exceptions=False)
    resp = c.get("/api/v1/notifications")
    assert resp.status_code == 401
