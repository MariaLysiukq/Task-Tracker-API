"""Database queries for ``Task``.

Functions only flush; the calling service owns the transaction and commits.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, func, not_, select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task, TaskPriority, TaskStatus


async def create(
    session: AsyncSession,
    *,
    project_id: int,
    title: str,
    description: str | None,
    status: TaskStatus,
    priority: TaskPriority,
    assignee_id: int | None,
    due_at: datetime | None,
) -> Task:
    """Insert a new task.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project_id : int
        Identifier of the owning project.
    title : str
        Task title.
    description : str | None
        Optional description.
    status : TaskStatus
        Workflow status.
    priority : TaskPriority
        Priority.
    assignee_id : int | None
        Assigned project member, or ``None``.
    due_at : datetime | None
        Timezone-aware deadline, or ``None``.

    Returns
    -------
    Task
        The flushed task with ``id`` and timestamps set.
    """
    task = Task(
        project_id=project_id,
        title=title,
        description=description,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        due_at=due_at,
    )
    session.add(task)
    await session.flush()
    return task


async def get_by_id(session: AsyncSession, task_id: int) -> Task | None:
    """Return a task by primary key.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    task_id : int
        Task identifier.

    Returns
    -------
    Task | None
        The task, or ``None`` if it does not exist.
    """
    return await session.get(Task, task_id)


def overdue_condition(now: datetime) -> ColumnElement[bool]:
    """Build the SQL condition for an overdue task.

    Parameters
    ----------
    now : datetime
        Current UTC moment.

    Returns
    -------
    ColumnElement[bool]
        ``due_at < now AND status != 'done'``.
    """
    return and_(Task.due_at.is_not(None), Task.due_at < now, Task.status != TaskStatus.DONE)


async def list_for_project(
    session: AsyncSession,
    project_id: int,
    *,
    status: TaskStatus | None,
    priority: TaskPriority | None,
    assignee_id: int | None,
    overdue: bool | None,
    now: datetime,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
) -> tuple[Sequence[Task], int]:
    """Return one filtered, sorted page of a project's tasks.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project_id : int
        Project identifier.
    status : TaskStatus | None
        Only tasks with this status, if given.
    priority : TaskPriority | None
        Only tasks with this priority, if given.
    assignee_id : int | None
        Only tasks assigned to this user, if given.
    overdue : bool | None
        ``True``: only overdue tasks; ``False``: only not overdue; ``None``: all.
    now : datetime
        Current UTC moment used for the overdue check.
    sort : str
        Sort column, ``created_at`` or ``id``.
    descending : bool
        Sort direction.
    limit : int
        Maximum number of items.
    offset : int
        Number of items to skip.

    Returns
    -------
    tuple[Sequence[Task], int]
        Page items and the total count; ``id`` breaks ties in the same direction.
    """
    conditions: list[ColumnElement[bool]] = [Task.project_id == project_id]
    if status is not None:
        conditions.append(Task.status == status)
    if priority is not None:
        conditions.append(Task.priority == priority)
    if assignee_id is not None:
        conditions.append(Task.assignee_id == assignee_id)
    if overdue is not None:
        conditions.append(overdue_condition(now) if overdue else not_(overdue_condition(now)))
    columns = [Task.created_at, Task.id] if sort == "created_at" else [Task.id]
    order_by = [column.desc() if descending else column.asc() for column in columns]
    total = await session.scalar(select(func.count()).select_from(Task).where(*conditions))
    items = await session.scalars(
        select(Task).where(*conditions).order_by(*order_by).limit(limit).offset(offset),
    )
    return items.all(), total or 0


async def update(session: AsyncSession, task: Task, values: Mapping[str, Any]) -> Task:
    """Apply field changes to a task.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    task : Task
        Persistent task to change.
    values : Mapping[str, Any]
        Column names mapped to new values.

    Returns
    -------
    Task
        The flushed task with ``updated_at`` refreshed.
    """
    for field, value in values.items():
        setattr(task, field, value)
    await session.flush()
    return task


async def delete(session: AsyncSession, task: Task) -> None:
    """Delete a task; its comments cascade in the database.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    task : Task
        Persistent task to delete.
    """
    await session.delete(task)
    await session.flush()


async def unassign_user_in_project(session: AsyncSession, project_id: int, user_id: int) -> None:
    """Clear ``assignee_id`` on every task of a project assigned to a user.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project_id : int
        Project identifier.
    user_id : int
        Assignee to remove.
    """
    await session.execute(
        sql_update(Task)
        .where(Task.project_id == project_id, Task.assignee_id == user_id)
        .values(assignee_id=None),
    )
