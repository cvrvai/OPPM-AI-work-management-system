"""Base repository for notification service."""

import uuid
from typing import Any, Type, TypeVar
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Base

T = TypeVar("T", bound=Base)


class BaseRepository:
    model: Type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_id(self, record_id: str | uuid.UUID) -> T | None:
        stmt = select(self.model).where(self.model.id == record_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> T:
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, record_id: str | uuid.UUID, data: dict) -> T | None:
        clean = {k: v for k, v in data.items() if v is not None}
        if not clean:
            return await self.find_by_id(record_id)
        stmt = update(self.model).where(self.model.id == record_id).values(**clean).returning(self.model)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def delete(self, record_id: str | uuid.UUID) -> bool:
        stmt = delete(self.model).where(self.model.id == record_id)
        await self.session.execute(stmt)
        await self.session.flush()
        return True
