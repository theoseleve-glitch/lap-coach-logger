"""Test harness — live Postgres via docker-compose.

The suite needs a real Postgres because the schema uses features SQLite
doesn't support (JSONB, ARRAY, UUID type, ``ON CONFLICT ... index_elements``
in the asyncpg dialect).

Before running:

    cd backend && docker-compose up -d postgres
    export TEST_DATABASE_URL=postgresql+asyncpg://lap_coach:lap_coach_dev_pw@localhost:5432/lap_coach_test
    # create empty DB: psql -h localhost -U lap_coach -c "CREATE DATABASE lap_coach_test"

Tests that require the DB skip automatically if ``TEST_DATABASE_URL`` is
not set, so CI without a Postgres container stays green (purely unit
tests still run).
"""

from __future__ import annotations

import asyncio
import os
import secrets
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.auth import hash_password
from app.config import get_settings
from app.database import Base, configure_engine, get_db


def _test_db_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


needs_db = pytest.mark.skipif(
    _test_db_url() is None,
    reason="TEST_DATABASE_URL not set — start docker-compose and export the URL",
)


@pytest_asyncio.fixture(scope="session")
async def _engine():
    """Configure the test engine once and hand it to every test."""
    url = _test_db_url()
    assert url, "needs_db gate should have skipped"
    configure_engine(url)
    # Ensure schema exists — simpler than running Alembic for unit tests.
    from app.database import _session_maker  # noqa: PLC2701 — internal for setup only
    assert _session_maker is not None
    async with _session_maker().bind.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Drop at the end so the next run starts clean.
    async with _session_maker().bind.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db(_engine) -> AsyncIterator[AsyncSession]:
    """Per-test session that truncates all tables afterwards."""
    async for session in get_db():
        yield session
        await session.rollback()

    # Fast cleanup — TRUNCATE ... CASCADE removes every row without needing
    # to respect FK insertion order.
    async for session in get_db():
        await session.execute(text(
            "TRUNCATE users, devices, sessions, laps, coaching_outputs, "
            "session_events, sync_envelopes, sync_failures CASCADE"
        ))
        await session.commit()


@pytest.fixture
def app():
    # Force a deterministic SECRET_KEY for tests so JWTs don't shift between runs.
    os.environ.setdefault("SECRET_KEY", "0" * 64)
    os.environ["DATABASE_URL"] = _test_db_url() or "postgresql+asyncpg://unused"
    get_settings.cache_clear()
    from app.main import create_app
    return create_app()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def make_user(db: AsyncSession, email: str, password: str = "hunter2hunter2") -> models.User:
    user = models.User(email=email.lower(), password_hash=hash_password(password), display_name=email)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def make_device(db: AsyncSession, user: models.User) -> models.Device:
    token = secrets.token_hex(32)
    device = models.Device(device_token=token, user_id=user.id, label="test")
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device
