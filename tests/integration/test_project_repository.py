"""Tests for ``app.repositories.project`` against the test database."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Membership, MembershipRole, Project, Task, User
from app.repositories import membership as membership_repo
from app.repositories import project as project_repo
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
    return await user_repo.create(session, email=email, hashed_password="hash", full_name="Ann")  # noqa: S106 - placeholder hash, not a secret


async def make_project(session: AsyncSession, owner: User, name: str = "Alpha") -> Project:
    """Create a project and its owner membership.

    Parameters
    ----------
    session : AsyncSession
        Test session.
    owner : User
        Owning user.
    name : str
        Project name.

    Returns
    -------
    Project
        Flushed project.
    """
    project = await project_repo.create(session, name=name, description=None, owner_id=owner.id)
    await membership_repo.create(
        session, project_id=project.id, user_id=owner.id, role=MembershipRole.OWNER
    )
    return project


async def test_create_and_get_by_id(db_session: AsyncSession) -> None:
    """Insert assigns an id and aware timestamps; lookup returns the project or ``None``."""
    owner = await make_user(db_session)
    project = await project_repo.create(
        db_session, name="Alpha", description="Docs", owner_id=owner.id
    )
    assert project.id is not None
    assert project.created_at.tzinfo is not None
    assert await project_repo.get_by_id(db_session, project.id) is project
    assert await project_repo.get_by_id(db_session, project.id + 1) is None


async def test_list_for_member_returns_only_own_projects_newest_first(
    db_session: AsyncSession,
) -> None:
    """Only projects with a membership are listed, ordered newest first, with a total."""
    ann = await make_user(db_session)
    bob = await make_user(db_session, "bob@example.com")
    first = await make_project(db_session, ann, "First")
    second = await make_project(db_session, ann, "Second")
    await make_project(db_session, bob, "Foreign")
    items, total = await project_repo.list_for_member(db_session, ann.id, limit=20, offset=0)
    assert [project.id for project in items] == [second.id, first.id]
    assert total == 2


async def test_list_for_member_paginates(db_session: AsyncSession) -> None:
    """``limit``/``offset`` slice the page while the total stays complete."""
    ann = await make_user(db_session)
    projects = [await make_project(db_session, ann, f"P{index}") for index in range(3)]
    items, total = await project_repo.list_for_member(db_session, ann.id, limit=1, offset=1)
    assert [project.id for project in items] == [projects[1].id]
    assert total == 3


async def test_list_for_member_without_projects(db_session: AsyncSession) -> None:
    """A user without memberships gets an empty page."""
    ann = await make_user(db_session)
    assert await project_repo.list_for_member(db_session, ann.id, limit=20, offset=0) == ([], 0)


async def test_update_changes_fields(db_session: AsyncSession) -> None:
    """Update applies values, including clearing the description."""
    owner = await make_user(db_session)
    project = await project_repo.create(
        db_session, name="Alpha", description="Docs", owner_id=owner.id
    )
    await project_repo.update(db_session, project, {"name": "Beta", "description": None})
    await db_session.refresh(project)
    assert project.name == "Beta"
    assert project.description is None


async def test_delete_cascades_memberships_and_tasks(db_session: AsyncSession) -> None:
    """Deleting a project removes its memberships and tasks in the database."""
    owner = await make_user(db_session)
    project = await make_project(db_session, owner)
    db_session.add(Task(project_id=project.id, title="Write docs"))
    await db_session.flush()
    await project_repo.delete(db_session, project)
    db_session.expunge_all()
    assert await project_repo.get_by_id(db_session, project.id) is None
    assert (await db_session.scalars(select(Membership))).all() == []
    assert (await db_session.scalars(select(Task))).all() == []


async def test_exists_owned_by(db_session: AsyncSession) -> None:
    """Only the owner of a project is reported as owning one."""
    ann = await make_user(db_session)
    bob = await make_user(db_session, "bob@example.com")
    await make_project(db_session, ann)
    assert await project_repo.exists_owned_by(db_session, ann.id)
    assert not await project_repo.exists_owned_by(db_session, bob.id)
