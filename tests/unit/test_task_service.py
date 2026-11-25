"""Unit tests for ``app.services.task``."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidDataError, NotFoundError
from app.models import Comment, Task, TaskPriority, TaskStatus
from app.schemas.common import SortOrder
from app.schemas.task import TaskCreate, TaskListParams, TaskSortField, TaskUpdate
from app.services import membership as membership_service
from app.services import project as project_service
from app.services import task as task_service
from tests.unit.service_helpers import make_team


async def test_create_task_by_member_with_defaults(db_session: AsyncSession) -> None:
    """A member creates a task; status and priority get their defaults."""
    project, _, member, _ = await make_team(db_session)
    task = await task_service.create_task(
        db_session, member, project.id, TaskCreate(title="Write docs")
    )
    assert (task.project_id, task.title) == (project.id, "Write docs")
    assert (task.status, task.priority, task.assignee_id) == (
        TaskStatus.TODO,
        TaskPriority.MEDIUM,
        None,
    )


async def test_create_task_with_member_assignee_and_due_at(db_session: AsyncSession) -> None:
    """Any project member, including the owner, can be the assignee; ``due_at`` is UTC."""
    project, owner, member, _ = await make_team(db_session)
    due_at = datetime(2030, 1, 1, 15, tzinfo=timezone(timedelta(hours=3)))
    task = await task_service.create_task(
        db_session,
        member,
        project.id,
        TaskCreate(title="Review", assignee_id=owner.id, due_at=due_at),
    )
    assert task.assignee_id == owner.id
    assert task.due_at == datetime(2030, 1, 1, 12, tzinfo=UTC)


async def test_create_task_hidden_from_outsider(db_session: AsyncSession) -> None:
    """A non-member or a missing project gives 404."""
    project, _, _, outsider = await make_team(db_session)
    data = TaskCreate(title="Write docs")
    for project_id in (project.id, project.id + 1):
        with pytest.raises(NotFoundError, match=project_service.PROJECT_NOT_FOUND):
            await task_service.create_task(db_session, outsider, project_id, data)


async def test_create_task_rejects_non_member_assignee(db_session: AsyncSession) -> None:
    """An assignee outside the project (or unknown) gives 422 and no task is stored."""
    project, owner, _, outsider = await make_team(db_session)
    for assignee_id in (outsider.id, 999):
        with pytest.raises(InvalidDataError, match=task_service.ASSIGNEE_NOT_MEMBER):
            await task_service.create_task(
                db_session, owner, project.id, TaskCreate(title="X", assignee_id=assignee_id)
            )
    assert (await db_session.scalars(select(Task))).all() == []


async def test_get_member_task(db_session: AsyncSession) -> None:
    """Members get the task; outsiders and missing ids get 404."""
    project, owner, member, outsider = await make_team(db_session)
    task = await task_service.create_task(db_session, owner, project.id, TaskCreate(title="X"))
    assert await task_service.get_member_task(db_session, member, task.id) is task
    for user, task_id in ((outsider, task.id), (member, task.id + 1)):
        with pytest.raises(NotFoundError, match=task_service.TASK_NOT_FOUND):
            await task_service.get_member_task(db_session, user, task_id)


async def test_update_task_by_member(db_session: AsyncSession) -> None:
    """A member changes fields of another member's task; omitted fields stay."""
    project, owner, member, _ = await make_team(db_session)
    task = await task_service.create_task(
        db_session, owner, project.id, TaskCreate(title="X", description="Docs")
    )
    updated = await task_service.update_task(
        db_session,
        member,
        task.id,
        TaskUpdate(status=TaskStatus.IN_PROGRESS, assignee_id=member.id),
    )
    assert (updated.title, updated.description) == ("X", "Docs")
    assert (updated.status, updated.assignee_id) == (TaskStatus.IN_PROGRESS, member.id)


async def test_update_task_without_assignee_keeps_it(db_session: AsyncSession) -> None:
    """An update that omits ``assignee_id`` leaves the assignee unchanged."""
    project, owner, member, _ = await make_team(db_session)
    task = await task_service.create_task(
        db_session, owner, project.id, TaskCreate(title="X", assignee_id=member.id)
    )
    updated = await task_service.update_task(
        db_session, owner, task.id, TaskUpdate(priority=TaskPriority.HIGH)
    )
    assert (updated.priority, updated.assignee_id) == (TaskPriority.HIGH, member.id)


async def test_update_task_clears_nullable_fields(db_session: AsyncSession) -> None:
    """Explicit ``null`` clears the assignee, description and deadline."""
    project, owner, _, _ = await make_team(db_session)
    task = await task_service.create_task(
        db_session,
        owner,
        project.id,
        TaskCreate(
            title="X",
            description="Docs",
            assignee_id=owner.id,
            due_at=datetime(2030, 1, 1, tzinfo=UTC),
        ),
    )
    data = TaskUpdate.model_validate({"assignee_id": None, "description": None, "due_at": None})
    updated = await task_service.update_task(db_session, owner, task.id, data)
    assert (updated.assignee_id, updated.description, updated.due_at) == (None, None, None)


async def test_update_task_rejects_non_member_assignee(db_session: AsyncSession) -> None:
    """Reassigning to a non-member gives 422 and keeps the old assignee."""
    project, owner, _, outsider = await make_team(db_session)
    task = await task_service.create_task(
        db_session, owner, project.id, TaskCreate(title="X", assignee_id=owner.id)
    )
    with pytest.raises(InvalidDataError, match=task_service.ASSIGNEE_NOT_MEMBER):
        await task_service.update_task(
            db_session, owner, task.id, TaskUpdate(assignee_id=outsider.id)
        )
    await db_session.refresh(task)
    assert task.assignee_id == owner.id


async def test_update_task_hidden_from_outsider(db_session: AsyncSession) -> None:
    """A non-member gets 404 when updating."""
    project, owner, _, outsider = await make_team(db_session)
    task = await task_service.create_task(db_session, owner, project.id, TaskCreate(title="X"))
    with pytest.raises(NotFoundError, match=task_service.TASK_NOT_FOUND):
        await task_service.update_task(db_session, outsider, task.id, TaskUpdate(title="Y"))


async def test_delete_task_by_member_cascades_comments(db_session: AsyncSession) -> None:
    """A member deletes a task and its comments."""
    project, owner, member, _ = await make_team(db_session)
    task = await task_service.create_task(db_session, owner, project.id, TaskCreate(title="X"))
    db_session.add(Comment(task_id=task.id, author_id=owner.id, body="Done?"))
    await db_session.commit()
    await task_service.delete_task(db_session, member, task.id)
    db_session.expunge_all()
    assert (await db_session.scalars(select(Task))).all() == []
    assert (await db_session.scalars(select(Comment))).all() == []


async def test_delete_task_hidden_from_outsider(db_session: AsyncSession) -> None:
    """A non-member gets 404 and the task stays."""
    project, owner, _, outsider = await make_team(db_session)
    task = await task_service.create_task(db_session, owner, project.id, TaskCreate(title="X"))
    with pytest.raises(NotFoundError, match=task_service.TASK_NOT_FOUND):
        await task_service.delete_task(db_session, outsider, task.id)
    assert await task_service.get_member_task(db_session, owner, task.id) is task


async def test_removed_member_loses_task_access(db_session: AsyncSession) -> None:
    """After removal a former member gets 404 for the project's tasks."""
    project, owner, member, _ = await make_team(db_session)
    task = await task_service.create_task(db_session, owner, project.id, TaskCreate(title="X"))
    await membership_service.remove_member(db_session, owner, project.id, member.id)
    with pytest.raises(NotFoundError, match=task_service.TASK_NOT_FOUND):
        await task_service.get_member_task(db_session, member, task.id)


async def test_list_tasks_filters_overdue_and_sorts(db_session: AsyncSession) -> None:
    """Members list tasks; overdue uses the current time and skips done tasks."""
    project, owner, member, _ = await make_team(db_session)
    past = datetime.now(UTC) - timedelta(hours=1)
    for data in (
        TaskCreate(title="late", due_at=past, assignee_id=member.id),
        TaskCreate(title="done-late", due_at=past, status=TaskStatus.DONE),
        TaskCreate(title="future", due_at=datetime.now(UTC) + timedelta(days=1)),
    ):
        await task_service.create_task(db_session, owner, project.id, data)
    items, total = await task_service.list_tasks(
        db_session, member, project.id, TaskListParams(overdue=True)
    )
    assert ([task.title for task in items], total) == (["late"], 1)
    items, total = await task_service.list_tasks(
        db_session,
        member,
        project.id,
        TaskListParams(sort=TaskSortField.ID, order=SortOrder.ASC, limit=2),
    )
    assert ([task.title for task in items], total) == (["late", "done-late"], 3)


async def test_list_tasks_hidden_from_outsider(db_session: AsyncSession) -> None:
    """A non-member or a missing project gives 404."""
    project, _, _, outsider = await make_team(db_session)
    for project_id in (project.id, project.id + 1):
        with pytest.raises(NotFoundError, match=project_service.PROJECT_NOT_FOUND):
            await task_service.list_tasks(db_session, outsider, project_id, TaskListParams())
