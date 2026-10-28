"""Task endpoints: creation and listing inside a project, access by task id."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.common import Page
from app.schemas.task import TaskCreate, TaskListParams, TaskRead, TaskUpdate
from app.services import task as task_service

router = APIRouter(tags=["tasks"])


@router.post("/projects/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: int,
    data: TaskCreate,
    user: CurrentUserDep,
    session: SessionDep,
) -> TaskRead:
    """Create a task in a project (any member).

    Parameters
    ----------
    project_id : int
        Project identifier.
    data : TaskCreate
        Task fields; ``due_at`` must include a timezone.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    TaskRead
        The created task (404 for non-members, 422 if the assignee is not a member).
    """
    return TaskRead.model_validate(await task_service.create_task(session, user, project_id, data))


@router.get("/projects/{project_id}/tasks")
async def list_tasks(
    project_id: int,
    params: Annotated[TaskListParams, Query()],
    user: CurrentUserDep,
    session: SessionDep,
) -> Page[TaskRead]:
    """List a project's tasks with filters, sorting and pagination (any member).

    Parameters
    ----------
    project_id : int
        Project identifier.
    params : TaskListParams
        ``status``, ``priority``, ``assignee_id``, ``overdue`` filters,
        ``sort`` (``created_at``/``id``), ``order`` (``desc``/``asc``), ``limit``, ``offset``.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    Page[TaskRead]
        One page of tasks with the total count (404 for non-members).
    """
    items, total = await task_service.list_tasks(session, user, project_id, params)
    return Page[TaskRead](
        items=[TaskRead.model_validate(item) for item in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, user: CurrentUserDep, session: SessionDep) -> TaskRead:
    """Return a task of the user's project.

    Parameters
    ----------
    task_id : int
        Task identifier.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    TaskRead
        The task (404 for non-members).
    """
    return TaskRead.model_validate(await task_service.get_member_task(session, user, task_id))


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    data: TaskUpdate,
    user: CurrentUserDep,
    session: SessionDep,
) -> TaskRead:
    """Update the sent fields of a task (any member).

    Parameters
    ----------
    task_id : int
        Task identifier.
    data : TaskUpdate
        Fields to change; ``null`` clears ``description``, ``assignee_id`` or ``due_at``.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    TaskRead
        The updated task (404 for non-members, 422 if the assignee is not a member).
    """
    return TaskRead.model_validate(await task_service.update_task(session, user, task_id, data))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, user: CurrentUserDep, session: SessionDep) -> None:
    """Delete a task and its comments (any member).

    Parameters
    ----------
    task_id : int
        Task identifier.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.
    """
    await task_service.delete_task(session, user, task_id)
