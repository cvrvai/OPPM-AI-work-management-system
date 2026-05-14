"""
Auth enforcement tests — every workspace-scoped endpoint must reject
a valid user who is NOT a member of the workspace.
Catches missing get_workspace_context dependency.
"""

import pytest
import uuid
from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock
from jose import JWTError
from jose import jwt

from domains.auth.service import exchange_external_token
from main import app
from shared.auth import CurrentUser, WorkspaceContext, get_current_user, require_owner
from shared.models.user import User

client = TestClient(app)
TEST_WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"
TEST_USER_ID = "22222222-2222-2222-2222-222222222222"


@contextmanager
def override_dependency(dependency, replacement):
    app.dependency_overrides[dependency] = replacement
    try:
        yield
    finally:
        app.dependency_overrides.pop(dependency, None)

WORKSPACE_SCOPED_ROUTES = [
    ("GET",  f"/api/v1/workspaces/{TEST_WORKSPACE_ID}/projects"),
    ("POST", f"/api/v1/workspaces/{TEST_WORKSPACE_ID}/projects"),
    ("GET",  f"/api/v1/workspaces/{TEST_WORKSPACE_ID}/tasks"),
    ("GET",  f"/api/v1/workspaces/{TEST_WORKSPACE_ID}/dashboard/stats"),
    ("GET",  f"/api/v1/workspaces/{TEST_WORKSPACE_ID}/objectives"),
    ("GET",  f"/api/v1/workspaces/{TEST_WORKSPACE_ID}/timeline"),
    ("GET",  f"/api/v1/workspaces/{TEST_WORKSPACE_ID}/costs"),
    ("GET",  f"/api/v1/workspaces/{TEST_WORKSPACE_ID}/notifications"),
]


@pytest.mark.parametrize("method,path", WORKSPACE_SCOPED_ROUTES)
def test_workspace_endpoint_requires_membership(method, path):
    """Every workspace-scoped endpoint must reject a valid user who
    is NOT a member of the workspace. Catches missing get_workspace_context."""
    mock_user = MagicMock(id=TEST_USER_ID, email="test@test.com", role="authenticated")

    with override_dependency(get_current_user, lambda: mock_user):
        response = client.request(method, path)

    assert response.status_code in (403, 404), (
        f"{method} {path} returned {response.status_code} — "
        "missing get_workspace_context dependency?"
    )


def test_unauthenticated_request_returns_401():
    """Requests without any authentication should get 401."""
    response = client.get(f"/api/v1/workspaces/{TEST_WORKSPACE_ID}/projects")
    assert response.status_code == 401


def test_require_owner_allows_owner_role():
    ws = WorkspaceContext(
        workspace_id=TEST_WORKSPACE_ID,
        user=MagicMock(id="user-1", email="owner@test.com", role="authenticated"),
        role="owner",
        member_id="member-1",
    )

    assert require_owner(ws) is ws


def test_require_owner_rejects_admin_role():
    ws = WorkspaceContext(
        workspace_id=TEST_WORKSPACE_ID,
        user=MagicMock(id="user-2", email="admin@test.com", role="authenticated"),
        role="admin",
        member_id="member-2",
    )

    with pytest.raises(HTTPException) as exc_info:
        require_owner(ws)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Workspace owner role required"


@pytest.mark.anyio
async def test_get_current_user_accepts_supabase_token_when_bridge_enabled():
    request = MagicMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="supabase-token")
    session = AsyncMock()
    settings = SimpleNamespace(
        jwt_secret_key="jwt-secret",
        jwt_algorithm="HS256",
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
        supabase_service_role_key="",
        supabase_auto_provision_users=True,
        supabase_bridge_workspace_id="bridge-workspace",
        supabase_bridge_role="member",
        supabase_auth_timeout_seconds=5.0,
    )

    with (
        patch("shared.auth.get_settings", return_value=settings),
        patch("shared.auth._decode_local_access_token", side_effect=JWTError("not an OPPM token")),
        patch(
            "shared.auth._fetch_supabase_identity",
            new=AsyncMock(return_value={
                "external_id": "supabase-user",
                "email": "one@example.com",
                "full_name": "One User",
                "avatar_url": None,
            }),
        ) as fetch_identity,
        patch(
            "shared.auth._resolve_supabase_current_user",
            new=AsyncMock(return_value=CurrentUser(id="oppm-user", email="one@example.com")),
        ) as resolve_current_user,
    ):
        user = await get_current_user(request, credentials, session)

    assert user.id == "oppm-user"
    assert user.email == "one@example.com"
    fetch_identity.assert_awaited_once_with("supabase-token", settings)
    resolve_current_user.assert_awaited_once()


@pytest.mark.anyio
async def test_get_current_user_rejects_invalid_token_without_supabase_bridge():
    request = MagicMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad-token")
    session = AsyncMock()
    settings = SimpleNamespace(
        jwt_secret_key="jwt-secret",
        jwt_algorithm="HS256",
        supabase_url="",
        supabase_anon_key="",
        supabase_service_role_key="",
        supabase_auto_provision_users=False,
        supabase_bridge_workspace_id="",
        supabase_bridge_role="member",
        supabase_auth_timeout_seconds=5.0,
    )

    with (
        patch("shared.auth.get_settings", return_value=settings),
        patch("shared.auth._decode_local_access_token", side_effect=JWTError("bad token")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(request, credentials, session)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


@pytest.mark.anyio
async def test_exchange_external_token_issues_local_oppm_tokens():
    session = SimpleNamespace(add=MagicMock(), commit=AsyncMock())
    user = User(
        id=uuid.UUID(TEST_USER_ID),
        email="one@example.com",
        hashed_password="hashed-password",
        auth_provider="supabase",
        external_subject="external-subject",
        full_name="One User",
        is_active=True,
        is_verified=True,
    )
    settings = SimpleNamespace(
        jwt_secret_key="jwt-secret",
        jwt_algorithm="HS256",
        access_token_expire_minutes=15,
        refresh_token_expire_days=30,
    )

    with (
        patch("domains.auth.service.get_settings", return_value=settings),
        patch(
            "domains.auth.service.resolve_supabase_user_from_token",
            new=AsyncMock(return_value=user),
        ) as resolve_user,
    ):
        response = await exchange_external_token(session, "supabase-token")

    decoded = jwt.decode(response["access_token"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])

    assert decoded["sub"] == TEST_USER_ID
    assert decoded["email"] == "one@example.com"
    assert response["refresh_token"]
    assert response["user"]["id"] == TEST_USER_ID
    resolve_user.assert_awaited_once_with(session, "supabase-token")
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
