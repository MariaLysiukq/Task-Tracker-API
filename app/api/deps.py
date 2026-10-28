"""Shared FastAPI dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.exceptions import UnauthorizedError
from app.models import User
from app.services import auth as auth_service

NOT_AUTHENTICATED = "Not authenticated"
# auto_error=False: a missing header must give 401, not FastAPI's default 403.
bearer_scheme = HTTPBearer(auto_error=False)


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


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Resolve the user from the ``Authorization: Bearer <token>`` header.

    Parameters
    ----------
    session : AsyncSession
        Request database session.
    credentials : HTTPAuthorizationCredentials | None
        Parsed bearer credentials, ``None`` if the header is missing or not Bearer.

    Returns
    -------
    User
        The authenticated user.

    Raises
    ------
    UnauthorizedError
        If the header is missing or the token is invalid.
    """
    if credentials is None:
        raise UnauthorizedError(NOT_AUTHENTICATED)
    return await auth_service.authenticate(session, credentials.credentials)


CurrentUserDep = Annotated[User, Depends(get_current_user)]
