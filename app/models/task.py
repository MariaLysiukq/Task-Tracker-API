"""Task model."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app._detail.constants import TASK_TITLE_MAX_LENGTH
from app.models.base import Base, TimestampMixin


class TaskStatus(StrEnum):
    """Workflow status of a task."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TaskPriority(StrEnum):
    """Priority of a task."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Task(TimestampMixin, Base):
    """Task inside a project, optionally assigned to a project member.

    ``assignee_id`` uses ``SET NULL`` so tasks survive account deletion.
    """

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_project_id_created_at_id", "project_id", "created_at", "id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(TASK_TITLE_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            name="task_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        default=TaskStatus.TODO,
        server_default=TaskStatus.TODO.value,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(
            TaskPriority,
            name="task_priority",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda priorities: [priority.value for priority in priorities],
        ),
        default=TaskPriority.MEDIUM,
        server_default=TaskPriority.MEDIUM.value,
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
