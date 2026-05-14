"""
Auth routes — login, signup, signout, refresh, and profile update.
Tokens returned in JSON body — frontend stores in localStorage.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import CurrentUser, get_current_user, security
from shared.database import get_session
from domains.auth.service import exchange_external_token, login, refresh_tokens, register, signout, update_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

class SignUpRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None

class RefreshRequest(BaseModel):
    refresh_token: str

class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    password: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/login")
async def login_route(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    """Sign in with email + password. Returns access + refresh tokens."""
    return await login(session, body.email, body.password)


@router.post("/signup")
async def signup_route(body: SignUpRequest, session: AsyncSession = Depends(get_session)):
    """Create a new account. Returns access + refresh tokens."""
    return await register(session, body.email, body.password, body.full_name)


@router.post("/refresh")
async def refresh_route(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    """Exchange a refresh token for new access + refresh tokens."""
    return await refresh_tokens(session, body.refresh_token)


@router.post("/exchange")
async def exchange_route(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_session),
):
    """Exchange a valid external bearer token for local OPPM platform tokens."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await exchange_external_token(session, credentials.credentials)


@router.post("/signout")
async def signout_route(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Invalidate all refresh tokens and blacklist access token."""
    # Extract the raw token from the request context
    # (get_current_user already validated it)
    await signout(session, current_user.id, "")
    return {"message": "Signed out"}


@router.get("/me")
async def me_route(current_user: CurrentUser = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
    }


@router.patch("/profile")
async def update_profile_route(
    body: UpdateProfileRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update display name or password for the current user."""
    if not body.full_name and not body.password:
        return {"message": "Nothing to update"}
    return await update_profile(session, current_user.id, body.full_name, body.password)
