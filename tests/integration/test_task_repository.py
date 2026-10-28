"""Tests for ``app.repositories.task`` against the test database."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment, Project, Task, TaskPriority, TaskStatus, User
from app.repositories import project as project_repo
from app.repositories import task as task_repo
from app.repositories import user as user_repo

NOW = datetime(2030, 1, 1, 12, tzinfo=UTC)


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


async def make_task(session: AsyncSession) -> tuple[Task, Project, User]:
    """Create a default task in a fresh project.

    Parameters
    ----------
    session : AsyncSession
        Test session.

    Returns
    -------
    tuple[Task, Project, User]
        Flushed task, its project and the project owner.
    """
    ann = await make_user(session, "ann@example.com")
    project = await project_repo.create(session, name="Alpha", description=None, owner_id=ann.id)
    task = await task_repo.create(
        session,
        project_id=project.id,
        title="Write docs",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        assignee_id=None,
        due_at=None,
    )
    return task, project, ann


async def test_create_and_get_by_id(db_session: AsyncSession) -> None:
    """A created task keeps all fields, has UTC timestamps and is found by id."""
    ann = await make_user(db_session, "ann@example.com")
    project = await project_repo.create(db_session, name="Alpha", description=None, owner_id=ann.id)
    due_at = datetime(2030, 1, 1, 12, tzinfo=UTC)
    task = await task_repo.create(
        db_session,
        project_id=project.id,
        title="Write docs",
        description="API",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        assignee_id=ann.id,
        due_at=due_at,
    )
    assert task.created_at.tzinfo is not None
    db_session.expunge_all()
    stored = await task_repo.get_by_id(db_session, task.id)
    assert stored is not None
    assert (stored.project_id, stored.title, stored.description) == (
        project.id,
        "Write docs",
        "API",
    )
    assert (stored.status, stored.priority) == (TaskStatus.IN_PROGRESS, TaskPriority.HIGH)
    assert stored.assignee_id == ann.id
    assert stored.due_at is not None
    assert stored.due_at.replace(tzinfo=UTC) == due_at
    assert await task_repo.get_by_id(db_session, task.id + 1) is None


async def test_update_changes_fields(db_session: AsyncSession) -> None:
    """Update applies values, including clearing nullable fields."""
    task, _, ann = await make_task(db_session)
    await task_repo.update(db_session, task, {"description": "API", "assignee_id": ann.id})
    await task_repo.update(
        db_session,
        task,
        {"title": "Ship", "status": TaskStatus.DONE, "description": None, "assignee_id": None},
    )
    await db_session.refresh(task)
    assert (task.title, task.status, task.description, task.assignee_id) == (
        "Ship",
        TaskStatus.DONE,
        None,
        None,
    )


async def test_delete_cascades_comments(db_session: AsyncSession) -> None:
    """Deleting a task removes it and its comments, but keeps the project."""
    task, project, ann = await make_task(db_session)
    db_session.add(Comment(task_id=task.id, author_id=ann.id, body="Looks good"))
    await db_session.flush()
    await task_repo.delete(db_session, task)
    db_session.expunge_all()
    assert await task_repo.get_by_id(db_session, task.id) is None
    assert (await db_session.scalars(select(Comment))).all() == []
    assert await project_repo.get_by_id(db_session, project.id) is not None


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


async def list_titles(db_session: AsyncSession, project_id: int, **overrides: Any) -> list[str]:
    """Return titles of one listed page with defaults for unspecified arguments.

    Parameters
    ----------
    db_session : AsyncSession
        Test session.
    project_id : int
        Project identifier.
    **overrides : Any
        Arguments of ``list_for_project`` to change.

    Returns
    -------
    list[str]
        Titles in listed order.
    """
    arguments: dict[str, Any] = {
        "status": None,
        "priority": None,
        "assignee_id": None,
        "overdue": None,
        "now": NOW,
        "sort": "created_at",
        "descending": True,
        "limit": 20,
        "offset": 0,
    } | overrides
    items, _ = await task_repo.list_for_project(db_session, project_id, **arguments)
    return [task.title for task in items]


async def make_listing(db_session: AsyncSession) -> tuple[Project, User]:
    """Create a project with varied tasks and one task in another project.

    Parameters
    ----------
    db_session : AsyncSession
        Test session.

    Returns
    -------
    tuple[Project, User]
        Project ``Alpha`` and its owner, the assignee of ``late``.
    """
    ann = await make_user(db_session, "ann@example.com")
    alpha = await project_repo.create(db_session, name="Alpha", description=None, owner_id=ann.id)
    beta = await project_repo.create(db_session, name="Beta", description=None, owner_id=ann.id)
    past, future = NOW - timedelta(days=1), NOW + timedelta(days=1)
    for task in (
        Task(project_id=alpha.id, title="late", due_at=past, assignee_id=ann.id),
        Task(project_id=alpha.id, title="done-late", due_at=past, status=TaskStatus.DONE),
        Task(project_id=alpha.id, title="soon", due_at=future, priority=TaskPriority.HIGH),
        Task(project_id=alpha.id, title="no-due", status=TaskStatus.IN_PROGRESS),
        Task(project_id=beta.id, title="other", due_at=past),
    ):
        db_session.add(task)
        await db_session.flush()
    return alpha, ann


async def test_list_for_project_filters(db_session: AsyncSession) -> None:
    """Each filter narrows the project's tasks; other projects never appear."""
    alpha, ann = await make_listing(db_session)
    assert await list_titles(db_session, alpha.id) == ["no-due", "soon", "done-late", "late"]
    assert await list_titles(db_session, alpha.id, status=TaskStatus.DONE) == ["done-late"]
    assert await list_titles(db_session, alpha.id, priority=TaskPriority.HIGH) == ["soon"]
    assert await list_titles(db_session, alpha.id, assignee_id=ann.id) == ["late"]
    assert await list_titles(db_session, alpha.id, status=TaskStatus.TODO, assignee_id=ann.id) == [
        "late",
    ]


async def test_list_for_project_overdue(db_session: AsyncSession) -> None:
    """Overdue means past ``due_at`` and not done; ``False`` returns the complement."""
    alpha, _ = await make_listing(db_session)
    assert await list_titles(db_session, alpha.id, overdue=True) == ["late"]
    assert await list_titles(db_session, alpha.id, overdue=False) == ["no-due", "soon", "done-late"]


async def test_list_for_project_sorting_and_pagination(db_session: AsyncSession) -> None:
    """Sort column and direction apply; ``total`` ignores ``limit`` and ``offset``."""
    alpha, _ = await make_listing(db_session)
    assert await list_titles(db_session, alpha.id, sort="id", descending=False) == [
        "late",
        "done-late",
        "soon",
        "no-due",
    ]
    assert await list_titles(db_session, alpha.id, descending=False, limit=2, offset=1) == [
        "done-late",
        "soon",
    ]
    items, total = await task_repo.list_for_project(
        db_session,
        alpha.id,
        status=None,
        priority=None,
        assignee_id=None,
        overdue=None,
        now=NOW,
        sort="created_at",
        descending=True,
        limit=1,
        offset=10,
    )
    assert (list(items), total) == ([], 4)
