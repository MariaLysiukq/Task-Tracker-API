"""Task rules: any project member manages tasks; the assignee must be a member.

A task is hidden (404) from users who are not members of its project;
an assignee outside the project is rejected with 422.
"""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app._detail.helpers import utc_now
from app.core.exceptions import InvalidDataError, NotFoundError
from app.models import Task, User
from app.repositories import membership as membership_repo
from app.repositories import task as task_repo
from app.schemas.common import SortOrder
from app.schemas.task import TaskCreate, TaskListParams, TaskUpdate
from app.services.project import get_member_project

TASK_NOT_FOUND = "Task not found"
ASSIGNEE_NOT_MEMBER = "Assignee must be a project member"


async def get_member_task(session: AsyncSession, user: User, task_id: int) -> Task:
    """Return a task from a project the user is a member of.

    Shared access check for tasks and their comments.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Authenticated user.
    task_id : int
        Task identifier.

    Returns
    -------
    Task
        The task.

    Raises
    ------
    NotFoundError
        If the task does not exist or the user is not a member of its project.
    """
    task = await task_repo.get_by_id(session, task_id)
    if task is None or await membership_repo.get(session, task.project_id, user.id) is None:
        raise NotFoundError(TASK_NOT_FOUND)
    return task


async def ensure_assignee_is_member(
    session: AsyncSession,
    project_id: int,
    assignee_id: int | None,
) -> None:
    """Check that an assignee, if given, is a current project member.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project_id : int
        Project identifier.
    assignee_id : int | None
        Proposed assignee; ``None`` means unassigned.

    Raises
    ------
    InvalidDataError
        If the assignee is not a member of the project.
    """
    if assignee_id is None:
        return
    if await membership_repo.get(session, project_id, assignee_id) is None:
        raise InvalidDataError(ASSIGNEE_NOT_MEMBER)


async def create_task(
    session: AsyncSession,
    user: User,
    project_id: int,
    data: TaskCreate,
) -> Task:
    """Create a task in a project the user is a member of.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    project_id : int
        Project identifier.
    data : TaskCreate
        Validated task data.

    Returns
    -------
    Task
        The new task.

    Raises
    ------
    NotFoundError
        If the project does not exist or the user is not a member.
    InvalidDataError
        If the assignee is not a project member.
    """
    await get_member_project(session, user, project_id)
    await ensure_assignee_is_member(session, project_id, data.assignee_id)
    task = await task_repo.create(session, project_id=project_id, **data.model_dump())
    await session.commit()
    return task


async def list_tasks(
    session: AsyncSession,
    user: User,
    project_id: int,
    params: TaskListParams,
) -> tuple[Sequence[Task], int]:
    """Return one filtered, sorted page of a project's tasks.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Authenticated user.
    project_id : int
        Project identifier.
    params : TaskListParams
        Filters, sorting and pagination.

    Returns
    -------
    tuple[Sequence[Task], int]
        Page items and the total count.

    Raises
    ------
    NotFoundError
        If the project does not exist or the user is not a member.
    """
    await get_member_project(session, user, project_id)
    return await task_repo.list_for_project(
        session,
        project_id,
        status=params.status,
        priority=params.priority,
        assignee_id=params.assignee_id,
        overdue=params.overdue,
        now=utc_now(),
        sort=params.sort,
        descending=params.order == SortOrder.DESC,
        limit=params.limit,
        offset=params.offset,
    )


async def update_task(session: AsyncSession, user: User, task_id: int, data: TaskUpdate) -> Task:
    """Apply a partial update to a task of the user's project.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    task_id : int
        Task identifier.
    data : TaskUpdate
        Fields sent by the client.

    Returns
    -------
    Task
        The updated task.

    Raises
    ------
    NotFoundError
        If the task does not exist or the user is not a member of its project.
    InvalidDataError
        If the new assignee is not a project member.
    """
    task = await get_member_task(session, user, task_id)
    changes = data.changes()
    if "assignee_id" in changes:
        await ensure_assignee_is_member(session, task.project_id, data.assignee_id)
    await task_repo.update(session, task, changes)
    await session.commit()
    return task


async def delete_task(session: AsyncSession, user: User, task_id: int) -> None:
    """Delete a task of the user's project; its comments cascade.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    task_id : int
        Task identifier.

    Raises
    ------
    NotFoundError
        If the task does not exist or the user is not a member of its project.
    """
    task = await get_member_task(session, user, task_id)
    await task_repo.delete(session, task)
    await session.commit()
