"""Async SQLAlchemy engine and session factory.

Both are created lazily so that importing the application does not require
database settings (tests override the session dependency).
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Return the cached async engine.

    Returns
    -------
    AsyncEngine
        Engine bound to ``DATABASE_URL``.
    """
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the cached session factory.

    Returns
    -------
    async_sessionmaker[AsyncSession]
        Factory producing sessions bound to the application engine.
    """
    return async_sessionmaker(get_engine(), expire_on_commit=False)
