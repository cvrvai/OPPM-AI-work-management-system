"""
Authentication and workspace authorization middleware.
Validates Supabase JWT tokens and checks workspace membership.
"""

import logging
from dataclasses import dataclass
from fastapi import Depends, HTTPException, status, Path, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from shared.database import get_db
from shared.config import get_settings

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


# ── Auth ──


@dataclass
class CurrentUser:
    """Authenticated user context injected into route handlers."""
    id: str
    email: str
    role: str = "authenticated"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """
    Validates the Supabase JWT by calling auth.get_user().
    Raises 401 if token is missing or invalid.
    """
    if not credentials:
        logger.debug("No credentials in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    logger.debug("Validating token: %s...%s", token[:20], token[-10:])

    try:
        db = get_db()
        response = db.auth.get_user(token)
        user = response.user
        if not user:
            raise ValueError("No user returned")
    except Exception as e:
        logger.warning("Token validation failed: %s: %s", type(e).__name__, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        id=str(user.id),
        email=user.email or "",
        role=getattr(user, "role", "authenticated") or "authenticated",
    )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser | None:
    """
    Optional auth — returns None instead of raising 401.
    Use for endpoints that work both authenticated and unauthenticated.
    """
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


# ── Workspace ──


@dataclass
class WorkspaceContext:
    """Workspace context injected into route handlers."""
    workspace_id: str
    user: CurrentUser
    role: str  # owner | admin | member | viewer
    member_id: str  # workspace_members.id

    @property
    def is_admin(self) -> bool:
        return self.role in ("owner", "admin")

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"

    @property
    def can_write(self) -> bool:
        return self.role in ("owner", "admin", "member")


async def get_workspace_context(
    workspace_id: str = Path(..., description="Workspace UUID"),
    user: CurrentUser = Depends(get_current_user),
) -> WorkspaceContext:
    """
    Dependency that verifies user is a member of the workspace.
    Returns WorkspaceContext with role information.
    """
    db = get_db()
    result = (
        db.table("workspace_members")
        .select("id, role")
        .eq("workspace_id", workspace_id)
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace",
        )

    return WorkspaceContext(
        workspace_id=workspace_id,
        user=user,
        role=result.data[0]["role"],
        member_id=result.data[0]["id"],
    )


def require_admin(ws: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
    """Dependency that requires admin or owner role."""
    if not ws.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner role required",
        )
    return ws


def require_write(ws: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
    """Dependency that requires at least member role (not viewer)."""
    if not ws.can_write:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access required (member, admin, or owner role)",
        )
    return ws


# ── Internal service-to-service auth ──


async def verify_internal_key(
    x_internal_api_key: str = Header(..., alias="X-Internal-API-Key"),
) -> bool:
    """Verify service-to-service API key for internal endpoints."""
    settings = get_settings()
    if not settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="INTERNAL_API_KEY not configured",
        )
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )
    return True
