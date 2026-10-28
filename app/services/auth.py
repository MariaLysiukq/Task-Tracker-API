"""Registration, login and access-token authentication."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models import User
from app.repositories import user as user_repo
from app.schemas.user import LoginRequest, UserCreate

EMAIL_TAKEN = "Email is already registered"
INVALID_CREDENTIALS = "Invalid email or password"


async def register(session: AsyncSession, data: UserCreate) -> User:
    """Create a user account.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    data : UserCreate
        Validated registration data.

    Returns
    -------
    User
        The new user.

    Raises
    ------
    ConflictError
        If the email is already registered.
    """
    if await user_repo.get_by_email(session, data.email) is not None:
        raise ConflictError(EMAIL_TAKEN)
    try:
        user = await user_repo.create(
            session,
            email=data.email,
            hashed_password=hash_password(data.password.get_secret_value()),
            full_name=data.full_name,
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise ConflictError(EMAIL_TAKEN) from error
    return user


async def login(session: AsyncSession, data: LoginRequest) -> str:
    """Check credentials and issue an access token.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    data : LoginRequest
        Email and password.

    Returns
    -------
    str
        Encoded JWT access token.

    Raises
    ------
    UnauthorizedError
        If the email is unknown or the password is wrong (same message for both).
    """
    user = await user_repo.get_by_email(session, data.email)
    hashed_password = user.hashed_password if user is not None else None
    if user is None or not verify_password(data.password.get_secret_value(), hashed_password):
        raise UnauthorizedError(INVALID_CREDENTIALS)
    return create_access_token(user.id)


async def authenticate(session: AsyncSession, token: str) -> User:
    """Resolve the user behind an access token.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    token : str
        Encoded JWT access token.

    Returns
    -------
    User
        The authenticated user.

    Raises
    ------
    UnauthorizedError
        If the token is invalid or its user no longer exists.
    """
    user = await user_repo.get_by_id(session, decode_access_token(token))
    if user is None:
        raise UnauthorizedError(INVALID_CREDENTIALS)
    return user
