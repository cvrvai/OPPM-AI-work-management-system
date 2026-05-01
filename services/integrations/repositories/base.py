"""Base repository for integrations service."""

import uuid
from typing import Any, Type, TypeVar
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Base

T = TypeVar("T", bound=Base)


class BaseRepository:
    """Generic async CRUD for integrations service."""

    model: Type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_id(self, record_id: str | uuid.UUID) -> T | None:
        stmt = select(self.model).where(self.model.id == record_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_all(
        self,
        filters: dict | None = None,
        order_by: str = "created_at",
        desc: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[T]:
        stmt = select(self.model)
        if filters:
            for k, v in filters.items():
                stmt = stmt.where(getattr(self.model, k) == v)
        col = getattr(self.model, order_by)
        stmt = stmt.order_by(col.desc() if desc else col.asc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict) -> T:
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, record_id: str | uuid.UUID, data: dict) -> T | None:
        stmt = (
            update(self.model)
            .where(self.model.id == record_id)
            .values(**data)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def delete(self, record_id: str | uuid.UUID) -> bool:
        stmt = delete(self.model).where(self.model.id == record_id)
        await self.session.execute(stmt)
        await self.session.flush()
        return True
