"""Unit tests for ``app.services.user``."""

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.security import verify_password
from app.models import Project, User
from app.repositories import user as user_repo
from app.schemas.user import UserCreate, UserUpdate
from app.services import auth
from app.services import user as user_service


async def make_user(session: AsyncSession, email: str = "ann@example.com") -> User:
    """Register a user through the auth service.

    Parameters
    ----------
    session : AsyncSession
        Test session.
    email : str
        Email to register.

    Returns
    -------
    User
        Registered user.
    """
    data = UserCreate(email=email, password=SecretStr("password123"), full_name="Ann")
    return await auth.register(session, data)


async def test_update_changes_only_sent_fields(db_session: AsyncSession) -> None:
    """Omitted fields keep their values."""
    user = await make_user(db_session)
    updated = await user_service.update_profile(db_session, user, UserUpdate(full_name="Anna"))
    assert updated.full_name == "Anna"
    assert updated.email == "ann@example.com"


async def test_update_password_stores_new_hash(db_session: AsyncSession) -> None:
    """A new password replaces the hash and the old one stops working."""
    user = await make_user(db_session)
    data = UserUpdate(password=SecretStr("new-password"))
    await user_service.update_profile(db_session, user, data)
    assert verify_password("new-password", user.hashed_password)
    assert not verify_password("password123", user.hashed_password)


async def test_update_email_to_own_email_is_allowed(db_session: AsyncSession) -> None:
    """Re-sending the current email is not a conflict."""
    user = await make_user(db_session)
    data = UserUpdate(email="ANN@example.com")
    assert (await user_service.update_profile(db_session, user, data)).email == "ann@example.com"


async def test_update_email_taken_by_other_user_conflicts(db_session: AsyncSession) -> None:
    """Another user's email is rejected with 409."""
    user = await make_user(db_session)
    await make_user(db_session, "bob@example.com")
    with pytest.raises(ConflictError):
        await user_service.update_profile(db_session, user, UserUpdate(email="bob@example.com"))


async def test_delete_account_without_projects(db_session: AsyncSession) -> None:
    """A user owning nothing is deleted."""
    user = await make_user(db_session)
    user_id = user.id
    await user_service.delete_account(db_session, user)
    assert await user_repo.get_by_id(db_session, user_id) is None


async def test_delete_account_owning_projects_conflicts(db_session: AsyncSession) -> None:
    """An owner must delete their projects first; the account stays."""
    user = await make_user(db_session)
    db_session.add(Project(name="Alpha", owner_id=user.id))
    await db_session.commit()
    with pytest.raises(ConflictError, match=user_service.OWNS_PROJECTS):
        await user_service.delete_account(db_session, user)
    assert await user_repo.get_by_id(db_session, user.id) is user
