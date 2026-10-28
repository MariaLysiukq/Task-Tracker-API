"""Tests for ``app.repositories.task`` against the test database."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task, User
from app.repositories import project as project_repo
from app.repositories import task as task_repo
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


async def test_unassign_user_in_project_touches_only_that_project_and_user(
    db_session: AsyncSession,
) -> None:
    """Only the user's tasks in the given project lose their assignee."""
    ann = await make_user(db_session, "ann@example.com")
    bob = await make_user(db_session, "bob@example.com")
    alpha = await project_repo.create(db_session, name="Alpha", description=None, owner_id=ann.id)
    beta = await project_repo.create(db_session, name="Beta", description=None, owner_id=ann.id)
    tasks = [
        Task(project_id=alpha.id, title="ann-alpha", assignee_id=ann.id),
        Task(project_id=alpha.id, title="bob-alpha", assignee_id=bob.id),
        Task(project_id=beta.id, title="ann-beta", assignee_id=ann.id),
    ]
    db_session.add_all(tasks)
    await db_session.flush()
    await task_repo.unassign_user_in_project(db_session, alpha.id, ann.id)
    for task in tasks:
        await db_session.refresh(task)
    assert [task.assignee_id for task in tasks] == [None, bob.id, ann.id]
