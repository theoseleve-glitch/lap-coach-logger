"""Async SQLAlchemy engine + session factory.

Usage inside request handlers:

    async def handler(db: AsyncSession = Depends(get_db)): ...

The engine is created lazily so tests can swap the URL before first use.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


_engine = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def _init() -> None:
    """Create the engine + sessionmaker from current settings.

    Called lazily on first get_db() to allow tests to call
    configure_engine(url) before any query runs.
    """
    global _engine, _session_maker
    if _engine is not None:
        return
    url = get_settings().database_url
    _engine = create_async_engine(url, pool_pre_ping=True, future=True)
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


def configure_engine(url: str) -> None:
    """Test hook: rebind engine to a different URL. Idempotent."""
    global _engine, _session_maker
    _engine = create_async_engine(url, pool_pre_ping=True, future=True)
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    _init()
    assert _session_maker is not None
    async with _session_maker() as session:
        yield session


async def dispose_engine() -> None:
    """Called on shutdown so connections close cleanly."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
