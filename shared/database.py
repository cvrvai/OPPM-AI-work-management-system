"""
SQLAlchemy async engine + session factory shared across all microservices.
"""

import logging
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from shared.config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    def __iter__(self):
        """Yield (db_col_name, value) pairs so dict(instance) works.
        Uses mapper inspection to correctly handle attrs with different Python/DB names
        (e.g., metadata_ → metadata).
        """
        from sqlalchemy import inspect as sa_inspect
        mapper = sa_inspect(type(self)).mapper
        for col_attr in mapper.column_attrs:
            db_col_name = col_attr.columns[0].name
            yield db_col_name, getattr(self, col_attr.key)

    def __getitem__(self, key: str):
        """Allow dict-style read access: instance['field'] using DB column name."""
        from sqlalchemy import inspect as sa_inspect
        mapper = sa_inspect(type(self)).mapper
        for col_attr in mapper.column_attrs:
            if col_attr.columns[0].name == key:
                return getattr(self, col_attr.key)
        return getattr(self, key)

    def get(self, key: str, default=None):
        """Allow dict-style .get() access using DB column name."""
        try:
            return self.__getitem__(key)
        except AttributeError:
            return default

    def to_dict(self) -> dict:
        return dict(self)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=(settings.environment == "development"),
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields an AsyncSession per request, auto-commits on success."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create engine and verify connectivity on startup."""
    engine = get_engine()
    async with engine.begin() as conn:
        logger.info("Database connection verified")


async def close_db() -> None:
    """Dispose engine on shutdown."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection closed")
