"""Unit tests for ORM metadata invariants required by the specification."""

from typing import Any

import pytest
from sqlalchemy import Column, DateTime, Enum, ForeignKey, UniqueConstraint

from app.models import Base, Comment, Membership, Task, TaskPriority, TaskStatus


def foreign_key(table: str, column: str) -> ForeignKey:
    """Return the single foreign key of a column.

    Parameters
    ----------
    table : str
        Table name.
    column : str
        Column name.

    Returns
    -------
    ForeignKey
        Foreign key declared on the column.
    """
    (key,) = Base.metadata.tables[table].c[column].foreign_keys
    return key


@pytest.mark.parametrize(
    ("table", "column", "target", "ondelete"),
    [
        ("projects", "owner_id", "users.id", "RESTRICT"),
        ("memberships", "project_id", "projects.id", "CASCADE"),
        ("memberships", "user_id", "users.id", "CASCADE"),
        ("tasks", "project_id", "projects.id", "CASCADE"),
        ("tasks", "assignee_id", "users.id", "SET NULL"),
        ("comments", "task_id", "tasks.id", "CASCADE"),
        ("comments", "author_id", "users.id", "CASCADE"),
    ],
)
def test_foreign_key_delete_rules(table: str, column: str, target: str, ondelete: str) -> None:
    """Project deletion cascades, owner deletion is restricted, assignee is nulled."""
    key = foreign_key(table, column)
    assert key.target_fullname == target
    assert key.ondelete == ondelete


def test_membership_pair_is_unique() -> None:
    """A user can be a member of a project only once."""
    uniques = {
        tuple(constraint.columns.keys())
        for constraint in Membership.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("project_id", "user_id") in uniques


def test_user_email_is_unique() -> None:
    """Email addresses cannot be registered twice."""
    assert Base.metadata.tables["users"].c["email"].unique is True


def test_all_datetime_columns_are_timezone_aware() -> None:
    """Every stored time value keeps its timezone (UTC)."""
    columns = [
        column
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, DateTime)
    ]
    assert columns
    assert all(column.type.timezone for column in columns)


def test_nullable_fields_match_specification() -> None:
    """Only optional fields from the specification are nullable."""
    nullable = {
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.nullable
    }
    assert nullable == {
        "projects.description",
        "tasks.description",
        "tasks.assignee_id",
        "tasks.due_at",
    }


@pytest.mark.parametrize(
    ("column", "values"),
    [
        (Task.__table__.c["status"], ["todo", "in_progress", "done"]),
        (Task.__table__.c["priority"], ["low", "medium", "high"]),
        (Membership.__table__.c["role"], ["owner", "member"]),
    ],
)
def test_enum_columns_store_lowercase_values(column: Column[Any], values: list[str]) -> None:
    """Enum columns persist the API values, not the Python member names."""
    assert isinstance(column.type, Enum)
    assert column.type.enums == values


def test_task_defaults() -> None:
    """New tasks default to ``todo`` status and ``medium`` priority."""
    status = Task.__table__.c["status"]
    priority = Task.__table__.c["priority"]
    assert status.default.arg == TaskStatus.TODO
    assert priority.default.arg == TaskPriority.MEDIUM
    assert status.server_default.arg == "todo"
    assert priority.server_default.arg == "medium"


def test_list_indexes_support_stable_sorting() -> None:
    """Task and comment lists are indexed by parent, creation time and id."""
    task_indexes = {tuple(index.columns.keys()) for index in Task.__table__.indexes}
    comment_indexes = {tuple(index.columns.keys()) for index in Comment.__table__.indexes}
    assert ("project_id", "created_at", "id") in task_indexes
    assert ("task_id", "created_at", "id") in comment_indexes
