"""Shared FastAPI dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session for one request.

    Yields
    ------
    AsyncSession
        Session closed after the response is sent.
    """
    async with get_session_factory()() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
