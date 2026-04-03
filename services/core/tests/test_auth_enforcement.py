"""
Auth enforcement tests — every workspace-scoped endpoint must reject
a valid user who is NOT a member of the workspace.
Catches missing get_workspace_context dependency.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from core.main import app

client = TestClient(app)

WORKSPACE_SCOPED_ROUTES = [
    ("GET",  "/api/v1/workspaces/ws-123/projects"),
    ("POST", "/api/v1/workspaces/ws-123/projects"),
    ("GET",  "/api/v1/workspaces/ws-123/tasks"),
    ("GET",  "/api/v1/workspaces/ws-123/dashboard/stats"),
    ("GET",  "/api/v1/workspaces/ws-123/objectives"),
    ("GET",  "/api/v1/workspaces/ws-123/timeline"),
    ("GET",  "/api/v1/workspaces/ws-123/costs"),
    ("GET",  "/api/v1/workspaces/ws-123/notifications"),
]


@pytest.mark.parametrize("method,path", WORKSPACE_SCOPED_ROUTES)
def test_workspace_endpoint_requires_membership(method, path):
    """Every workspace-scoped endpoint must reject a valid user who
    is NOT a member of the workspace. Catches missing get_workspace_context."""
    mock_user = MagicMock(id="user-not-in-workspace", email="test@test.com", role="authenticated")

    with patch("shared.auth.get_current_user", return_value=mock_user):
        response = client.request(method, path)

    assert response.status_code in (403, 404), (
        f"{method} {path} returned {response.status_code} — "
        "missing get_workspace_context dependency?"
    )


def test_unauthenticated_request_returns_401():
    """Requests without any authentication should get 401."""
    response = client.get("/api/v1/workspaces/ws-123/projects")
    assert response.status_code == 401
