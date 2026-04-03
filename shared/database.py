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
    pass


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
    """FastAPI dependency — yields an AsyncSession per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


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
