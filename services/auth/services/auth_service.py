"""
Auth service — register, login, refresh, signout with bcrypt + JWT.
Business logic only — raises domain exceptions, never HTTPException.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from shared.models.user import User, RefreshToken
from shared.redis_client import get_redis
from exceptions.auth_errors import AuthConflictError, AuthUnauthorizedError, AuthNotFoundError

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _create_access_token(user: User) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": "authenticated",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def _token_response(user: User, access_token: str, raw_refresh: str) -> dict:
    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": get_settings().access_token_expire_minutes * 60,
        "user": {"id": str(user.id), "email": user.email, "full_name": user.full_name},
    }


async def register(
    session: AsyncSession, email: str, password: str, full_name: str | None = None
) -> dict:
    result = await session.execute(select(User).where(User.email == email).limit(1))
    if result.scalar_one_or_none():
        raise AuthConflictError("Email already registered")

    user = User(
        email=email,
        hashed_password=_hash_password(password),
        full_name=full_name,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    access_token = _create_access_token(user)
    raw_refresh = _create_refresh_token()
    session.add(RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_expire_days),
    ))
    await session.commit()
    return _token_response(user, access_token, raw_refresh)


async def login(session: AsyncSession, email: str, password: str) -> dict:
    result = await session.execute(select(User).where(User.email == email).limit(1))
    user = result.scalar_one_or_none()

    if not user or not _verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = _create_access_token(user)
    raw_refresh = _create_refresh_token()
    session.add(RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_expire_days),
    ))
    await session.commit()
    return _token_response(user, access_token, raw_refresh)


async def refresh_tokens(session: AsyncSession, raw_refresh_token: str) -> dict:
    token_hash = _hash_token(raw_refresh_token)
    result = await session.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        ).limit(1)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    rt.revoked = True
    user_result = await session.execute(select(User).where(User.id == rt.user_id).limit(1))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")

    access_token = _create_access_token(user)
    new_raw_refresh = _create_refresh_token()
    session.add(RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(new_raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_expire_days),
    ))
    await session.commit()
    return _token_response(user, access_token, new_raw_refresh)


async def signout(session: AsyncSession, user_id: str, access_token: str) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)
        .values(revoked=True)
    )
    await session.commit()

    if access_token:
        try:
            settings = get_settings()
            redis = get_redis()
            if redis:
                await redis.setex(
                    f"blacklist:{access_token}",
                    settings.access_token_expire_minutes * 60,
                    "1",
                )
        except Exception as exc:
            logger.warning("Failed to blacklist token in Redis: %s", exc)


async def update_profile(session: AsyncSession, user_id: str, data: dict) -> dict:
    result = await session.execute(select(User).where(User.id == user_id).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthNotFoundError()

    if "full_name" in data:
        user.full_name = data["full_name"]
    if "password" in data:
        user.hashed_password = _hash_password(data["password"])

    await session.commit()
    return {"message": "Profile updated"}
