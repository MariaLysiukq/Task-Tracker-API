"""Unit tests for ``app.services.auth``."""

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.schemas.user import LoginRequest, UserCreate
from app.services import auth


def registration(email: str = "Ann@Example.com") -> UserCreate:
    """Build a valid registration request.

    Parameters
    ----------
    email : str
        Email as typed by the client.

    Returns
    -------
    UserCreate
        Validated request.
    """
    return UserCreate(email=email, password=SecretStr("password123"), full_name="Ann")


def credentials(
    email: str = "ann@example.com",
    password: str = "password123",  # noqa: S107 - test fixture value
) -> LoginRequest:
    """Build a login request.

    Parameters
    ----------
    email : str
        Login email.
    password : str
        Plain password.

    Returns
    -------
    LoginRequest
        Validated request.
    """
    return LoginRequest(email=email, password=SecretStr(password))


async def test_register_stores_hash_and_lowercase_email(db_session: AsyncSession) -> None:
    """The password is stored only as a verifiable hash; email is normalized."""
    user = await auth.register(db_session, registration())
    assert user.email == "ann@example.com"
    assert user.hashed_password != "password123"  # noqa: S105 - test fixture value
    assert verify_password("password123", user.hashed_password)


async def test_register_duplicate_email_conflicts(db_session: AsyncSession) -> None:
    """Emails differing only in case are the same account."""
    await auth.register(db_session, registration())
    with pytest.raises(ConflictError):
        await auth.register(db_session, registration("ANN@example.com"))


async def test_login_returns_token_for_user(db_session: AsyncSession, settings: Settings) -> None:
    """Valid credentials give a token that authenticates the same user."""
    user = await auth.register(db_session, registration())
    token = await auth.login(db_session, credentials("ANN@example.com"))
    assert await auth.authenticate(db_session, token) is user


@pytest.mark.parametrize(
    ("email", "password"),
    [("ann@example.com", "wrong-password"), ("nobody@example.com", "password123")],
    ids=["wrong-password", "unknown-email"],
)
async def test_login_rejects_bad_credentials(
    db_session: AsyncSession,
    settings: Settings,
    email: str,
    password: str,
) -> None:
    """Wrong password and unknown email fail with the same message."""
    await auth.register(db_session, registration())
    with pytest.raises(UnauthorizedError, match=auth.INVALID_CREDENTIALS):
        await auth.login(db_session, credentials(email, password))


async def test_authenticate_rejects_token_of_missing_user(
    db_session: AsyncSession,
    settings: Settings,
) -> None:
    """A valid token for a deleted or never-existing user is 401."""
    with pytest.raises(UnauthorizedError):
        await auth.authenticate(db_session, create_access_token(999))


async def test_authenticate_rejects_invalid_token(
    db_session: AsyncSession,
    settings: Settings,
) -> None:
    """A malformed token is 401."""
    with pytest.raises(UnauthorizedError):
        await auth.authenticate(db_session, "not-a-token")
