"""Async database foundation.

Provides a SQLAlchemy 2 ``DeclarativeBase`` and a lazily-created async
engine/session factory. No connection is opened at import time (FR-005);
the engine is created on first use.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from exambrain_shared.config import get_settings
from exambrain_shared.errors import NotConfiguredError


class Base(DeclarativeBase):
    """Declarative base for all ExamBrain ORM models."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(database_url: str | None = None) -> AsyncEngine:
    """Return the async engine, creating it lazily on first use."""
    global _engine
    if _engine is None:
        url = database_url or get_settings().database_url
        if not url:
            raise NotConfiguredError("Database", "set DATABASE_URL")
        _engine = create_async_engine(url)
    return _engine


def get_session_factory(
    database_url: str | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Return the async session factory, creating it lazily on first use."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(database_url), expire_on_commit=False
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield an ``AsyncSession`` (FastAPI dependency style)."""
    async with get_session_factory()() as session:
        yield session
