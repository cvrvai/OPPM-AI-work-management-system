"""
Base repository — generic async CRUD for the auth service.
Mirrors services/core/repositories/base.py.
"""

import uuid
from typing import Any, Type, TypeVar
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database import Base

T = TypeVar("T", bound=Base)


class BaseRepository:
    model: Type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_id(self, record_id: str | uuid.UUID) -> T | None:
        result = await self.session.execute(
            select(self.model).where(self.model.id == record_id).limit(1)
        )
        return result.scalar_one_or_none()

    async def find_all(
        self,
        filters: dict[str, Any] | None = None,
        order_by: str = "created_at",
        desc: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[T]:
        stmt = select(self.model)
        if filters:
            for k, v in filters.items():
                stmt = stmt.where(getattr(self.model, k) == v)
        col = getattr(self.model, order_by)
        stmt = stmt.order_by(col.desc() if desc else col.asc())
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict) -> T:
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, record_id: str | uuid.UUID, data: dict) -> T | None:
        clean = {k: v for k, v in data.items() if v is not None}
        if not clean:
            return await self.find_by_id(record_id)
        stmt = (
            update(self.model)
            .where(self.model.id == record_id)
            .values(**clean)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()
