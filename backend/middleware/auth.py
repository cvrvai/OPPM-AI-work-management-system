"""
JWT authentication middleware.
Validates Supabase JWT tokens via the Supabase Auth API.
"""

import logging
from dataclasses import dataclass
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_db

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


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
