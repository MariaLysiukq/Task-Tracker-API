"""Shared pytest fixtures."""

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import Settings, get_settings
from app.main import create_app
from app.models import Base

# Dedicated test PostgreSQL if configured, otherwise in-memory SQLite; never ``DATABASE_URL``.
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Point application settings at the test database and a test JWT key.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to set environment variables for this test only.

    Yields
    ------
    Settings
        Settings built from the patched environment.
    """
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session on freshly created tables, dropped afterwards.

    Yields
    ------
    AsyncSession
        Session bound to the test database.
    """
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def app() -> FastAPI:
    """Return a fresh application instance.

    Returns
    -------
    FastAPI
        Application isolated from other tests.
    """
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Yield an HTTP client bound to the application in-process.

    Parameters
    ----------
    app : FastAPI
        Application under test.

    Yields
    ------
    AsyncClient
        Client sending requests through ``ASGITransport``.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
