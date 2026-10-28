"""Tests for ``app.repositories.user`` against the test database."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import user as user_repo


async def make_user(session: AsyncSession, email: str = "ann@example.com") -> User:
    """Create a user with fixed name and hash.

    Parameters
    ----------
    session : AsyncSession
        Test session.
    email : str
        Email to register.

    Returns
    -------
    User
        Flushed user.
    """
    return await user_repo.create(session, email=email, hashed_password="hash", full_name="Ann")


async def test_create_sets_id_and_aware_timestamps(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    assert user.id is not None
    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None


async def test_create_duplicate_email_raises(db_session: AsyncSession) -> None:
    await make_user(db_session)
    with pytest.raises(IntegrityError):
        await make_user(db_session)


async def test_get_by_id(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    assert await user_repo.get_by_id(db_session, user.id) is user
    assert await user_repo.get_by_id(db_session, user.id + 1) is None


async def test_get_by_email(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await make_user(db_session, "bob@example.com")
    assert await user_repo.get_by_email(db_session, "ann@example.com") is user
    assert await user_repo.get_by_email(db_session, "nobody@example.com") is None


async def test_update_changes_fields_and_updated_at(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    before = user.updated_at
    updated = await user_repo.update(db_session, user, {"full_name": "Anna", "email": "a@x.io"})
    assert updated.full_name == "Anna"
    assert updated.email == "a@x.io"
    assert updated.updated_at > before
    assert await user_repo.get_by_email(db_session, "a@x.io") is user


async def test_update_to_taken_email_raises(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    await make_user(db_session, "bob@example.com")
    with pytest.raises(IntegrityError):
        await user_repo.update(db_session, user, {"email": "bob@example.com"})


async def test_delete(db_session: AsyncSession) -> None:
    user = await make_user(db_session)
    user_id = user.id
    await user_repo.delete(db_session, user)
    assert await user_repo.get_by_id(db_session, user_id) is None
