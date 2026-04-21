"""
Authentication and workspace authorization middleware.
Validates JWT tokens locally via python-jose HS256 and checks workspace membership.
"""

import logging
import time
from dataclasses import dataclass
from fastapi import Depends, Header, HTTPException, Request, status, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.config import get_settings
from shared.database import get_session
from shared.models.workspace import WorkspaceMember

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
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser:
    """
    Validates JWT locally using HS256.
    Reads token from Authorization: Bearer header.
    Raises 401 if token is missing or invalid.
    """
    token: str | None = None

    if credentials:
        token = credentials.credentials

    if not token:
        logger.debug("No credentials in request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("Validating token: %s...%s", token[:20], token[-10:])

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str | None = payload.get("sub")
        email: str | None = payload.get("email")
        if not user_id:
            raise JWTError("Missing sub claim")
        return CurrentUser(
            id=user_id,
            email=email or "",
            role=payload.get("role", "authenticated"),
        )
    except JWTError as e:
        logger.warning("Token validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> CurrentUser | None:
    """
    Optional auth — returns None instead of raising 401.
    Use for endpoints that work both authenticated and unauthenticated.
    """
    if not credentials:
        return None
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


# ── Workspace membership cache ──

_membership_cache: dict[tuple, tuple] = {}
_CACHE_TTL = 60  # seconds


def invalidate_membership_cache(user_id: str, workspace_id: str):
    """Call when removing a member or changing their role."""
    _membership_cache.pop((user_id, workspace_id), None)


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
    session: AsyncSession = Depends(get_session),
) -> WorkspaceContext:
    """
    Dependency that verifies user is a member of the workspace.
    Uses in-process cache to avoid repeated DB calls on the same page load.
    """
    cache_key = (user.id, workspace_id)
    now = time.time()

    # Check cache first
    if cache_key in _membership_cache:
        role, member_id, expires_at = _membership_cache[cache_key]
        if now < expires_at:
            return WorkspaceContext(
                workspace_id=workspace_id,
                user=user,
                role=role,
                member_id=member_id,
            )

    result = await session.execute(
        select(WorkspaceMember.id, WorkspaceMember.role)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
        .limit(1)
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this workspace",
        )

    member_id = str(row.id)
    role = row.role
    _membership_cache[cache_key] = (role, member_id, now + _CACHE_TTL)

    return WorkspaceContext(
        workspace_id=workspace_id,
        user=user,
        role=role,
        member_id=member_id,
    )


def require_admin(ws: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
    """Dependency that requires admin or owner role."""
    if not ws.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or owner role required",
        )
    return ws


def require_owner(ws: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
    """Dependency that requires the workspace owner role."""
    if not ws.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace owner role required",
        )
    return ws


def require_write(ws: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
    """Dependency that requires at least member role (owner, admin, or member — not viewer)."""
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
