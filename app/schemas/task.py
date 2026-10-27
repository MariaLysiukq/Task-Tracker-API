"""Schemas for tasks and the task list query."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import PositiveInt, StringConstraints

from app._detail.constants import TASK_TITLE_MAX_LENGTH
from app.models import TaskPriority, TaskStatus
from app.schemas.common import (
    PageParams,
    PatchModel,
    ReadModel,
    RequestModel,
    SortOrder,
    UTCDateTime,
)
from app.schemas.project import Description

TaskTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=TASK_TITLE_MAX_LENGTH),
]


class TaskSortField(StrEnum):
    """Columns allowed for sorting the task list."""

    CREATED_AT = "created_at"
    ID = "id"


class TaskCreate(RequestModel):
    """Task creation request body; ``due_at`` must include a timezone."""

    title: TaskTitle
    description: Description | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: PositiveInt | None = None
    due_at: UTCDateTime | None = None


class TaskUpdate(PatchModel):
    """Partial task update; ``description``, ``assignee_id`` and ``due_at`` may be cleared."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"description", "assignee_id", "due_at"},
    )
    title: TaskTitle | None = None
    description: Description | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: PositiveInt | None = None
    due_at: UTCDateTime | None = None


class TaskRead(ReadModel):
    """Task representation."""

    id: int
    project_id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee_id: int | None
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskListParams(PageParams):
    """Filters, sorting and pagination for the task list.

    Attributes
    ----------
    status : TaskStatus or None
        Only tasks with this status.
    priority : TaskPriority or None
        Only tasks with this priority.
    assignee_id : int or None
        Only tasks assigned to this user.
    overdue : bool or None
        ``True``: only overdue tasks; ``False``: only not overdue tasks.
    sort : TaskSortField
        Sort column; ``id`` is always the tie-breaker.
    order : SortOrder
        Sort direction.
    """

    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: PositiveInt | None = None
    overdue: bool | None = None
    sort: TaskSortField = TaskSortField.CREATED_AT
    order: SortOrder = SortOrder.DESC
