"""User repository for the auth service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shared.models.user import User, RefreshToken
from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    model = User

    async def find_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email).limit(1)
        )
        return result.scalar_one_or_none()


class RefreshTokenRepository(BaseRepository):
    model = RefreshToken

    async def find_valid(self, token_hash: str):
        from datetime import datetime, timezone
        from sqlalchemy import and_
        result = await self.session.execute(
            select(RefreshToken).where(
                and_(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.revoked == False,
                )
            ).limit(1)
        )
        return result.scalar_one_or_none()
