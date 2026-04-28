"""Auth v1 routes — login, signup, signout, refresh, me, profile update."""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import get_current_user, CurrentUser
from shared.database import get_session
from services.auth_service import register, login, refresh_tokens, signout, update_profile
from schemas.auth import (
    LoginRequest,
    SignUpRequest,
    RefreshRequest,
    UpdateProfileRequest,
    TokenResponse,
)
from exceptions.auth_errors import AuthNotFoundError, AuthConflictError
from fastapi import HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth")


@router.post("/login", response_model=TokenResponse)
async def login_route(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    """Sign in with email + password. Returns access + refresh tokens."""
    return await login(session, body.email, body.password)


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup_route(body: SignUpRequest, session: AsyncSession = Depends(get_session)):
    """Create a new account. Returns access + refresh tokens."""
    try:
        return await register(session, body.email, body.password, body.full_name)
    except AuthConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/refresh", response_model=TokenResponse)
async def refresh_route(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    """Exchange a refresh token for new access + refresh tokens."""
    return await refresh_tokens(session, body.refresh_token)


@router.post("/signout")
async def signout_route(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Invalidate all refresh tokens for the current user."""
    await signout(session, current_user.id, "")
    return {"message": "Signed out"}


@router.get("/me")
async def me_route(current_user: CurrentUser = Depends(get_current_user)):
    """Return the authenticated user's profile from JWT."""
    return {"id": current_user.id, "email": current_user.email, "role": current_user.role}


@router.patch("/profile")
async def update_profile_route(
    body: UpdateProfileRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update the authenticated user's full_name and/or password."""
    return await update_profile(session, current_user.id, body.model_dump(exclude_none=True))
