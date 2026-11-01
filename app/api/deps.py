"""Shared FastAPI dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.exceptions import TooManyRequestsError, UnauthorizedError
from app.core.rate_limit import RateLimiter
from app.models import User
from app.schemas.common import PageParams
from app.services import auth as auth_service

NOT_AUTHENTICATED = "Not authenticated"
TOO_MANY_REQUESTS = "Too many requests, try again later"
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
PageDep = Annotated[PageParams, Query()]


def enforce_rate_limit(limiter: RateLimiter, request: Request) -> None:
    """Count a request against a limiter, keyed by the client IP.

    Behind a reverse proxy the client IP is the proxy's unless uvicorn runs with
    ``--proxy-headers`` and ``--forwarded-allow-ips`` set to the proxy address.

    Parameters
    ----------
    limiter : RateLimiter
        Limiter for the endpoint.
    request : Request
        Incoming request.

    Raises
    ------
    TooManyRequestsError
        If the client exceeded the limit.
    """
    key = request.client.host if request.client is not None else "unknown"
    if not limiter.hit(key):
        raise TooManyRequestsError(TOO_MANY_REQUESTS)


async def login_rate_limit(request: Request) -> None:
    """Limit login attempts per client IP.

    Parameters
    ----------
    request : Request
        Incoming request; the limiter lives in ``app.state.login_limiter``.
    """
    enforce_rate_limit(request.app.state.login_limiter, request)


async def register_rate_limit(request: Request) -> None:
    """Limit registrations per client IP.

    Parameters
    ----------
    request : Request
        Incoming request; the limiter lives in ``app.state.register_limiter``.
    """
    enforce_rate_limit(request.app.state.register_limiter, request)
