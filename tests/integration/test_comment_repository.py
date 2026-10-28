"""Tests for ``app.repositories.comment`` against the test database."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task, User
from app.repositories import comment as comment_repo
from app.repositories import project as project_repo
from app.repositories import user as user_repo


async def make_task(session: AsyncSession) -> tuple[Task, User]:
    """Create a user, a project and one task in it.

    Parameters
    ----------
    session : AsyncSession
        Test session.

    Returns
    -------
    tuple[Task, User]
        Flushed task and the user.
    """
    ann = await user_repo.create(
        session,
        email="ann@example.com",
        hashed_password="hash",  # noqa: S106
        full_name="Ann",
    )
    project = await project_repo.create(session, name="Alpha", description=None, owner_id=ann.id)
    task = Task(project_id=project.id, title="Write docs")
    session.add(task)
    await session.flush()
    return task, ann


async def test_create_get_and_update_body(db_session: AsyncSession) -> None:
    """A created comment is found by id and its body can be replaced."""
    task, ann = await make_task(db_session)
    comment = await comment_repo.create(db_session, task_id=task.id, author_id=ann.id, body="Hi")
    assert comment.created_at.tzinfo is not None
    db_session.expunge_all()
    stored = await comment_repo.get_by_id(db_session, comment.id)
    assert stored is not None
    assert (stored.task_id, stored.author_id, stored.body) == (task.id, ann.id, "Hi")
    await comment_repo.update_body(db_session, stored, "Edited")
    db_session.expunge_all()
    stored = await comment_repo.get_by_id(db_session, comment.id)
    assert stored is not None
    assert stored.body == "Edited"
    assert await comment_repo.get_by_id(db_session, comment.id + 1) is None


async def test_list_for_task_paginates_newest_first(db_session: AsyncSession) -> None:
    """Only the task's comments are listed, newest first, with the total count."""
    task, ann = await make_task(db_session)
    other = Task(project_id=task.project_id, title="Other")
    db_session.add(other)
    await db_session.flush()
    for body in ("first", "second", "third"):
        await comment_repo.create(db_session, task_id=task.id, author_id=ann.id, body=body)
    await comment_repo.create(db_session, task_id=other.id, author_id=ann.id, body="other")
    items, total = await comment_repo.list_for_task(db_session, task.id, limit=2, offset=0)
    assert ([comment.body for comment in items], total) == (["third", "second"], 3)
    items, total = await comment_repo.list_for_task(db_session, task.id, limit=2, offset=2)
    assert ([comment.body for comment in items], total) == (["first"], 3)


async def test_delete(db_session: AsyncSession) -> None:
    """A deleted comment is no longer found."""
    task, ann = await make_task(db_session)
    comment = await comment_repo.create(db_session, task_id=task.id, author_id=ann.id, body="Hi")
    await comment_repo.delete(db_session, comment)
    assert await comment_repo.get_by_id(db_session, comment.id) is None
