"""
Canonical BaseRepository — the single source of truth for async CRUD.
All domain repositories inherit from this class.

Usage:
    from shared.base_repository import BaseRepository

    class MyRepo(BaseRepository):
        model = MyModel
"""

import uuid
from typing import Any, Type, TypeVar
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Base

T = TypeVar("T", bound=Base)


class BaseRepository:
    """Generic async CRUD with optional workspace scoping."""

    model: Type[T]

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Read ──

    async def find_by_id(self, record_id: str | uuid.UUID) -> T | None:
        stmt = select(self.model).where(self.model.id == record_id).limit(1)
        result = await self.session.execute(stmt)
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

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        stmt = select(func.count(self.model.id))
        if filters:
            for k, v in filters.items():
                stmt = stmt.where(getattr(self.model, k) == v)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    # ── Write ──

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

    async def delete(self, record_id: str | uuid.UUID) -> bool:
        stmt = delete(self.model).where(self.model.id == record_id)
        await self.session.execute(stmt)
        await self.session.flush()
        return True

    # ── Workspace-scoped helpers ──

    async def find_all_in_workspace(
        self,
        workspace_id: str,
        extra_filters: dict[str, Any] | None = None,
        order_by: str = "created_at",
        desc: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[T]:
        filters = {"workspace_id": workspace_id}
        if extra_filters:
            filters.update(extra_filters)
        return await self.find_all(filters=filters, order_by=order_by, desc=desc, limit=limit, offset=offset)

    async def count_in_workspace(self, workspace_id: str, extra_filters: dict[str, Any] | None = None) -> int:
        filters = {"workspace_id": workspace_id}
        if extra_filters:
            filters.update(extra_filters)
        return await self.count(filters=filters)
