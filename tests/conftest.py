"""Shared pytest fixtures."""

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

from app.api import deps
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


def enable_sqlite_foreign_keys(connection: DBAPIConnection, _: ConnectionPoolEntry) -> None:
    """Turn on foreign key enforcement, which SQLite disables by default.

    Parameters
    ----------
    connection : DBAPIConnection
        Freshly opened DBAPI connection.
    _ : ConnectionPoolEntry
        Pool record (unused).
    """
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Yield an engine on freshly created tables, dropped afterwards.

    Yields
    ------
    AsyncEngine
        Engine bound to the test database.
    """
    engine = create_async_engine(TEST_DB_URL)
    if engine.dialect.name == "sqlite":
        event.listen(engine.sync_engine, "connect", enable_sqlite_foreign_keys)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the test engine.

    Parameters
    ----------
    db_engine : AsyncEngine
        Test engine.

    Returns
    -------
    async_sessionmaker[AsyncSession]
        Factory configured like the application one.
    """
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a session on the test database.

    Parameters
    ----------
    session_factory : async_sessionmaker[AsyncSession]
        Test session factory.

    Yields
    ------
    AsyncSession
        Session bound to the test database.
    """
    async with session_factory() as session:
        yield session


@pytest.fixture
def app(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> FastAPI:
    """Return a fresh application wired to the test database.

    Parameters
    ----------
    settings : Settings
        Test settings (JWT key).
    session_factory : async_sessionmaker[AsyncSession]
        Test session factory replacing the application one.
    monkeypatch : pytest.MonkeyPatch
        Used to swap the factory behind ``get_session``.

    Returns
    -------
    FastAPI
        Application isolated from other tests.
    """
    monkeypatch.setattr(deps, "get_session_factory", lambda: session_factory)
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
