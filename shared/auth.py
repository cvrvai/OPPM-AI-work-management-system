"""
Authentication and workspace authorization middleware.
Validates JWT tokens locally via python-jose HS256 and checks workspace membership.
"""

import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass
import bcrypt
import httpx
from fastapi import Depends, Header, HTTPException, Request, status, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.config import get_settings
from shared.database import get_session
from shared.models.user import User
from shared.models.workspace import WorkspaceMember
from shared.redis_client import get_redis

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
_SUPABASE_TOKEN_CACHE_TTL = 60
_SUPABASE_PROVIDER = "supabase"
_supabase_token_cache: dict[str, tuple[dict, float]] = {}


# ── Auth ──


@dataclass
class CurrentUser:
    """Authenticated user context injected into route handlers."""
    id: str
    email: str
    role: str = "authenticated"


def _decode_local_access_token(token: str, settings) -> CurrentUser:
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


def _is_supabase_auth_enabled(settings) -> bool:
    return bool(settings.supabase_url and (settings.supabase_anon_key or settings.supabase_service_role_key))


def _build_supabase_token_cache_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _build_external_password_placeholder() -> str:
    random_secret = secrets.token_urlsafe(32)
    return bcrypt.hashpw(random_secret.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


async def _find_user_by_external_subject(session: AsyncSession, provider: str, external_subject: str) -> User | None:
    if not external_subject:
        return None

    result = await session.execute(
        select(User)
        .where(
            User.auth_provider == provider,
            User.external_subject == external_subject,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _fetch_supabase_identity(token: str, settings) -> dict:
    cache_key = _build_supabase_token_cache_key(token)
    now = time.time()
    cached = _supabase_token_cache.get(cache_key)
    if cached and now < cached[1]:
        return cached[0]

    api_key = settings.supabase_service_role_key or settings.supabase_anon_key
    if not api_key:
        raise JWTError("Supabase auth bridge is missing an API key")

    userinfo_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    try:
        async with httpx.AsyncClient(timeout=settings.supabase_auth_timeout_seconds) as client:
            response = await client.get(
                userinfo_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": api_key,
                },
            )
    except httpx.HTTPError as exc:
        logger.warning("Supabase auth lookup failed: %s", exc)
        raise JWTError("Supabase auth lookup failed") from exc

    if response.status_code != status.HTTP_200_OK:
        raise JWTError("Invalid or expired Supabase token")

    payload = response.json()
    email = payload.get("email")
    if not isinstance(email, str) or not email:
        raise JWTError("Supabase token did not include an email")

    user_metadata = payload.get("user_metadata") or {}
    full_name_value = user_metadata.get("full_name") or user_metadata.get("name")
    avatar_url_value = user_metadata.get("avatar_url")
    identity = {
        "provider": _SUPABASE_PROVIDER,
        "external_subject": payload.get("id") or payload.get("sub") or "",
        "external_id": payload.get("id") or payload.get("sub") or "",
        "email": email.lower(),
        "full_name": full_name_value if isinstance(full_name_value, str) and full_name_value else None,
        "avatar_url": avatar_url_value if isinstance(avatar_url_value, str) and avatar_url_value else None,
    }
    _supabase_token_cache[cache_key] = (identity, now + _SUPABASE_TOKEN_CACHE_TTL)
    return identity


async def _ensure_supabase_bridge_membership(session: AsyncSession, user: User, identity: dict, settings) -> None:
    if not settings.supabase_bridge_workspace_id:
        return

    result = await session.execute(
        select(WorkspaceMember.id)
        .where(
            WorkspaceMember.workspace_id == settings.supabase_bridge_workspace_id,
            WorkspaceMember.user_id == user.id,
        )
        .limit(1)
    )
    if result.first():
        return

    session.add(
        WorkspaceMember(
            workspace_id=settings.supabase_bridge_workspace_id,
            user_id=user.id,
            role=settings.supabase_bridge_role,
            display_name=identity.get("full_name"),
            avatar_url=identity.get("avatar_url"),
        )
    )
    await session.flush()


def _apply_supabase_identity_to_user(user: User, identity: dict) -> None:
    if identity.get("full_name") and not user.full_name:
        user.full_name = identity["full_name"]
    if identity.get("avatar_url") and not user.avatar_url:
        user.avatar_url = identity["avatar_url"]

    external_subject = identity.get("external_subject") or identity.get("external_id") or ""
    if external_subject and user.external_subject != external_subject:
        user.external_subject = external_subject
    if user.auth_provider != _SUPABASE_PROVIDER:
        user.auth_provider = _SUPABASE_PROVIDER


async def _get_or_provision_supabase_user(session: AsyncSession, identity: dict, settings) -> User:
    external_subject = identity.get("external_subject") or identity.get("external_id") or ""
    user = await _find_user_by_external_subject(session, _SUPABASE_PROVIDER, external_subject)

    if not user:
        result = await session.execute(select(User).where(User.email == identity["email"]).limit(1))
        user = result.scalar_one_or_none()

    if not user:
        if not settings.supabase_auto_provision_users:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supabase account is not linked to an OPPM user",
            )

        user = User(
            email=identity["email"],
            hashed_password=_build_external_password_placeholder(),
            auth_provider=_SUPABASE_PROVIDER,
            external_subject=external_subject or None,
            full_name=identity.get("full_name"),
            is_active=True,
            is_verified=True,
            avatar_url=identity.get("avatar_url"),
        )
        session.add(user)
        await session.flush()
    else:
        _apply_supabase_identity_to_user(user, identity)

    return user


async def _resolve_supabase_current_user(session: AsyncSession, identity: dict, settings) -> CurrentUser:
    user = await _get_or_provision_supabase_user(session, identity, settings)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    await _ensure_supabase_bridge_membership(session, user, identity, settings)
    await session.flush()

    return CurrentUser(id=str(user.id), email=user.email, role="authenticated")


async def resolve_supabase_user_from_token(session: AsyncSession, token: str, settings=None) -> User:
    settings = settings or get_settings()
    if not _is_supabase_auth_enabled(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase auth bridge is not configured",
        )

    try:
        identity = await _fetch_supabase_identity(token, settings)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await _get_or_provision_supabase_user(session, identity, settings)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    await _ensure_supabase_bridge_membership(session, user, identity, settings)
    await session.flush()
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_session),
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
        return _decode_local_access_token(token, settings)
    except JWTError as local_error:
        if _is_supabase_auth_enabled(settings):
            try:
                identity = await _fetch_supabase_identity(token, settings)
                return await _resolve_supabase_current_user(session, identity, settings)
            except HTTPException:
                raise
            except JWTError as supabase_error:
                logger.warning("Token validation failed: local=%s supabase=%s", local_error, supabase_error)
        else:
            logger.warning("Token validation failed: %s", local_error)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser | None:
    """
    Optional auth — returns None instead of raising 401.
    Use for endpoints that work both authenticated and unauthenticated.
    """
    if not credentials:
        return None
    try:
        return await get_current_user(request, credentials, session)
    except HTTPException:
        return None


# ── Workspace membership cache ──
# Two-tier cache: L1 = in-process (fast), L2 = Redis (shared across instances)

_membership_cache: dict[tuple, tuple] = {}
_CACHE_TTL = 60  # seconds
_REDIS_PREFIX = "auth:membership:"


def _membership_redis_key(user_id: str, workspace_id: str) -> str:
    return f"{_REDIS_PREFIX}{user_id}:{workspace_id}"


def invalidate_membership_cache(user_id: str, workspace_id: str):
    """Call when removing a member or changing their role.
    Clears both L1 in-process cache and L2 Redis cache."""
    _membership_cache.pop((user_id, workspace_id), None)
    # Best-effort Redis invalidation — do not block or fail if Redis is unavailable
    try:
        import asyncio
        redis = get_redis()
        if asyncio.iscoroutine(redis):
            # get_redis is async — fire-and-forget in a new task if event loop is running
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_redis_delete(user_id, workspace_id))
            except RuntimeError:
                # No event loop running — skip async Redis invalidation
                pass
        else:
            # Synchronous path (should not happen with async redis_client)
            key = _membership_redis_key(user_id, workspace_id)
            redis.delete(key)  # type: ignore[union-attr]
    except Exception:
        pass


async def _redis_delete(user_id: str, workspace_id: str) -> None:
    try:
        redis = await get_redis()
        key = _membership_redis_key(user_id, workspace_id)
        await redis.delete(key)
    except Exception as e:
        logger.warning("Redis membership cache invalidation failed: %s", e)


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
    Uses two-tier cache (L1 in-process + L2 Redis) to avoid repeated DB calls.
    Falls back to DB if both caches miss or Redis is unavailable.
    """
    cache_key = (user.id, workspace_id)
    now = time.time()

    # L1: Check in-process cache first (fastest)
    if cache_key in _membership_cache:
        role, member_id, expires_at = _membership_cache[cache_key]
        if now < expires_at:
            return WorkspaceContext(
                workspace_id=workspace_id,
                user=user,
                role=role,
                member_id=member_id,
            )

    # L2: Check Redis cache (shared across instances)
    redis_hit = None
    try:
        redis = await get_redis()
        key = _membership_redis_key(user.id, workspace_id)
        cached = await redis.get(key)
        if cached:
            data = json.loads(cached)
            if now < data["expires_at"]:
                redis_hit = (data["role"], data["member_id"])
                # Warm L1 cache
                _membership_cache[cache_key] = (data["role"], data["member_id"], data["expires_at"])
                return WorkspaceContext(
                    workspace_id=workspace_id,
                    user=user,
                    role=data["role"],
                    member_id=data["member_id"],
                )
    except Exception as e:
        logger.warning("Redis membership cache read failed, falling back to DB: %s", e)

    # Cache miss — query database
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
    expires_at = now + _CACHE_TTL

    # Store in L1 in-process cache
    _membership_cache[cache_key] = (role, member_id, expires_at)

    # Store in L2 Redis cache (best-effort)
    try:
        redis = await get_redis()
        key = _membership_redis_key(user.id, workspace_id)
        await redis.setex(
            key,
            _CACHE_TTL,
            json.dumps({"role": role, "member_id": member_id, "expires_at": expires_at}),
        )
    except Exception as e:
        logger.warning("Redis membership cache write failed: %s", e)

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
