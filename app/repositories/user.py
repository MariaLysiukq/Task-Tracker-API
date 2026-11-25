"""Database queries for ``User``.

Functions only flush; the calling service owns the transaction and commits.
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Return a user by primary key.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user_id : int
        User identifier.

    Returns
    -------
    User | None
        The user, or ``None`` if it does not exist.
    """
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    """Return a user by normalized (lowercase) email.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    email : str
        Lowercase email address.

    Returns
    -------
    User | None
        The user, or ``None`` if the email is not registered.
    """
    result = await session.scalars(select(User).where(User.email == email))
    return result.one_or_none()


async def create(
    session: AsyncSession,
    *,
    email: str,
    hashed_password: str,
    full_name: str,
) -> User:
    """Insert a new user.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    email : str
        Lowercase email address.
    hashed_password : str
        Password hash (never the plain password).
    full_name : str
        Display name.

    Returns
    -------
    User
        The flushed user with ``id`` and timestamps set.

    Raises
    ------
    sqlalchemy.exc.IntegrityError
        If the email is already registered.
    """
    user = User(email=email, hashed_password=hashed_password, full_name=full_name)
    session.add(user)
    await session.flush()
    return user


async def update(session: AsyncSession, user: User, values: Mapping[str, Any]) -> User:
    """Apply field changes to a user.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Persistent user to change.
    values : Mapping[str, Any]
        Column names mapped to new values (``email``, ``full_name``, ``hashed_password``).

    Returns
    -------
    User
        The flushed user with ``updated_at`` refreshed.

    Raises
    ------
    sqlalchemy.exc.IntegrityError
        If the new email is already registered.
    """
    for field, value in values.items():
        setattr(user, field, value)
    await session.flush()
    return user


async def delete(session: AsyncSession, user: User) -> None:
    """Delete a user; memberships cascade and assigned tasks are unassigned in the database.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Persistent user to delete.

    Raises
    ------
    sqlalchemy.exc.IntegrityError
        If the user still owns projects (``RESTRICT``).
    """
    await session.delete(user)
    await session.flush()
