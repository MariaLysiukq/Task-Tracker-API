"""Tests for ``app.repositories.membership`` against the test database."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MembershipRole, Project, User
from app.repositories import membership as membership_repo
from app.repositories import project as project_repo
from app.repositories import user as user_repo


async def make_user(session: AsyncSession, email: str) -> User:
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
    return await user_repo.create(session, email=email, hashed_password="hash", full_name="Ann")  # noqa: S106


async def make_project(session: AsyncSession) -> tuple[Project, User]:
    """Create a project owned by a fresh user, without memberships.

    Parameters
    ----------
    session : AsyncSession
        Test session.

    Returns
    -------
    tuple[Project, User]
        Flushed project and its owner.
    """
    owner = await make_user(session, "owner@example.com")
    project = await project_repo.create(session, name="Alpha", description=None, owner_id=owner.id)
    return project, owner


async def test_create_and_get(db_session: AsyncSession) -> None:
    """A created membership is found by project and user; others are ``None``."""
    project, owner = await make_project(db_session)
    membership = await membership_repo.create(
        db_session, project_id=project.id, user_id=owner.id, role=MembershipRole.OWNER
    )
    assert membership.created_at.tzinfo is not None
    assert await membership_repo.get(db_session, project.id, owner.id) is membership
    assert await membership_repo.get(db_session, project.id, owner.id + 1) is None


async def test_create_duplicate_raises(db_session: AsyncSession) -> None:
    """The ``(project_id, user_id)`` pair is unique."""
    project, owner = await make_project(db_session)
    await membership_repo.create(
        db_session, project_id=project.id, user_id=owner.id, role=MembershipRole.OWNER
    )
    with pytest.raises(IntegrityError):
        await membership_repo.create(
            db_session, project_id=project.id, user_id=owner.id, role=MembershipRole.MEMBER
        )


async def test_create_for_missing_user_raises(db_session: AsyncSession) -> None:
    """A membership must reference an existing user (foreign keys enforced)."""
    project, _ = await make_project(db_session)
    with pytest.raises(IntegrityError):
        await membership_repo.create(
            db_session, project_id=project.id, user_id=999, role=MembershipRole.MEMBER
        )


async def test_list_for_project_newest_first_and_paginated(db_session: AsyncSession) -> None:
    """Members of one project are listed newest first; ``limit``/``offset`` slice the page."""
    project, owner = await make_project(db_session)
    other_project = await project_repo.create(
        db_session, name="Beta", description=None, owner_id=owner.id
    )
    await membership_repo.create(
        db_session, project_id=project.id, user_id=owner.id, role=MembershipRole.OWNER
    )
    await membership_repo.create(
        db_session, project_id=other_project.id, user_id=owner.id, role=MembershipRole.OWNER
    )
    bob = await make_user(db_session, "bob@example.com")
    await membership_repo.create(
        db_session, project_id=project.id, user_id=bob.id, role=MembershipRole.MEMBER
    )
    items, total = await membership_repo.list_for_project(
        db_session, project.id, limit=20, offset=0
    )
    assert [membership.user_id for membership in items] == [bob.id, owner.id]
    assert total == 2
    items, total = await membership_repo.list_for_project(db_session, project.id, limit=1, offset=1)
    assert [membership.user_id for membership in items] == [owner.id]
    assert total == 2
