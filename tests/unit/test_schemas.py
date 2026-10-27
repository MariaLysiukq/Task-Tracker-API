"""Unit tests for request/response schema validation rules."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from app._detail.constants import (
    PAGE_LIMIT_DEFAULT,
    PAGE_LIMIT_MAX,
    PASSWORD_MIN_LENGTH,
    TASK_TITLE_MAX_LENGTH,
)
from app.models import Membership, MembershipRole, TaskPriority, TaskStatus, User
from app.schemas.comment import CommentCreate
from app.schemas.common import Page, PageParams, SortOrder
from app.schemas.project import MemberRead, ProjectCreate, ProjectUpdate
from app.schemas.task import TaskCreate, TaskListParams, TaskSortField, TaskUpdate
from app.schemas.user import LoginRequest, UserCreate, UserRead, UserUpdate

VALID_USER = {"email": "Alice@Example.COM", "password": "s3cret-pass", "full_name": " Alice "}


def test_user_create_normalizes_email_and_name() -> None:
    """Email is lowercased and the full name is stripped."""
    user = UserCreate.model_validate(VALID_USER)
    assert user.email == "alice@example.com"
    assert user.full_name == "Alice"
    assert user.password.get_secret_value() == "s3cret-pass"


@pytest.mark.parametrize(
    "override",
    [
        {"email": "not-an-email"},
        {"password": "x" * (PASSWORD_MIN_LENGTH - 1)},
        {"full_name": "   "},
        {"role": "owner"},
    ],
)
def test_user_create_rejects_invalid_data(override: dict[str, Any]) -> None:
    """Bad email, short password, blank name and unknown fields are rejected."""
    with pytest.raises(ValidationError):
        UserCreate.model_validate(VALID_USER | override)


def test_password_is_hidden_in_repr() -> None:
    """Plain passwords never appear in the string form of a request."""
    login = LoginRequest.model_validate({"email": "a@example.com", "password": "topsecret"})
    assert "topsecret" not in repr(login)
    assert "topsecret" not in login.model_dump_json()


def test_user_read_has_no_password_field() -> None:
    """The response schema cannot expose the password hash."""
    now = datetime.now(UTC)
    stored_hash = "$argon2id$v=19$fake"
    user = User(
        id=1,
        email="a@example.com",
        hashed_password=stored_hash,
        full_name="A",
        created_at=now,
        updated_at=now,
    )
    dumped = UserRead.model_validate(user).model_dump()
    assert "hashed_password" not in dumped
    assert "password" not in dumped
    assert dumped["email"] == "a@example.com"


def test_patch_keeps_only_sent_fields() -> None:
    """Omitted fields are not reported as changes."""
    update = UserUpdate.model_validate({"full_name": "Bob"})
    assert update.changes() == {"full_name": "Bob"}


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (UserUpdate, {"email": None}),
        (ProjectUpdate, {"name": None}),
        (TaskUpdate, {"title": None}),
        (TaskUpdate, {"status": None}),
    ],
)
def test_patch_rejects_null_for_required_fields(
    schema: type[UserUpdate | ProjectUpdate | TaskUpdate],
    payload: dict[str, Any],
) -> None:
    """Explicit ``null`` for a non-nullable column is a validation error."""
    with pytest.raises(ValidationError, match="cannot be null"):
        schema.model_validate(payload)


def test_patch_allows_clearing_nullable_fields() -> None:
    """Nullable task fields can be cleared with ``null``."""
    update = TaskUpdate.model_validate({"assignee_id": None, "due_at": None, "description": None})
    assert update.changes() == {"assignee_id": None, "due_at": None, "description": None}


def test_project_create_strips_and_limits_name() -> None:
    """Project names are stripped and must not be blank."""
    assert ProjectCreate.model_validate({"name": "  Apollo  "}).name == "Apollo"
    with pytest.raises(ValidationError):
        ProjectCreate.model_validate({"name": " "})


def test_task_create_defaults() -> None:
    """New tasks default to ``todo``/``medium`` without assignee or deadline."""
    task = TaskCreate.model_validate({"title": "Write tests"})
    assert task.status is TaskStatus.TODO
    assert task.priority is TaskPriority.MEDIUM
    assert task.assignee_id is None
    assert task.due_at is None


@pytest.mark.parametrize("length", [0, TASK_TITLE_MAX_LENGTH + 1])
def test_task_title_length_bounds(length: int) -> None:
    """Task titles must be 1 to 150 characters."""
    with pytest.raises(ValidationError):
        TaskCreate.model_validate({"title": "x" * length})


def test_task_title_max_length_is_accepted() -> None:
    """A title of exactly 150 characters is valid."""
    title = "x" * TASK_TITLE_MAX_LENGTH
    assert TaskCreate.model_validate({"title": title}).title == title


def test_task_due_at_is_converted_to_utc() -> None:
    """An offset datetime is stored as the same instant in UTC."""
    task = TaskCreate.model_validate({"title": "t", "due_at": "2026-01-01T12:00:00+02:00"})
    assert task.due_at == datetime(2026, 1, 1, 10, tzinfo=UTC)
    assert task.due_at is not None
    assert task.due_at.tzinfo is UTC


@pytest.mark.parametrize("schema", [TaskCreate, TaskUpdate])
def test_task_due_at_rejects_naive_datetime(schema: type[TaskCreate | TaskUpdate]) -> None:
    """A datetime without timezone is ambiguous and rejected."""
    with pytest.raises(ValidationError):
        schema.model_validate({"title": "t", "due_at": "2026-01-01T12:00:00"})


@pytest.mark.parametrize(
    "payload",
    [{"status": "blocked"}, {"priority": "urgent"}, {"assignee_id": 0}],
)
def test_task_create_rejects_invalid_values(payload: dict[str, Any]) -> None:
    """Unknown enum values and non-positive ids are rejected."""
    with pytest.raises(ValidationError):
        TaskCreate.model_validate({"title": "t"} | payload)


def test_page_params_defaults() -> None:
    """Pagination defaults to the first page of 20 items."""
    params = PageParams()
    assert (params.limit, params.offset) == (PAGE_LIMIT_DEFAULT, 0)


@pytest.mark.parametrize(
    "payload",
    [{"limit": 0}, {"limit": PAGE_LIMIT_MAX + 1}, {"offset": -1}],
)
def test_page_params_bounds(payload: dict[str, int]) -> None:
    """``limit`` outside 1..100 and negative ``offset`` are rejected."""
    with pytest.raises(ValidationError):
        PageParams.model_validate(payload)


def test_task_list_params_parse_query_strings() -> None:
    """Query string values are coerced into typed filters."""
    params = TaskListParams.model_validate(
        {"status": "done", "overdue": "true", "sort": "id", "order": "asc", "limit": "5"},
    )
    assert params.status is TaskStatus.DONE
    assert params.overdue is True
    assert params.sort is TaskSortField.ID
    assert params.order is SortOrder.ASC
    assert params.limit == 5


def test_task_list_params_default_sort() -> None:
    """Default order is newest first by creation time."""
    params = TaskListParams()
    assert (params.sort, params.order) == (TaskSortField.CREATED_AT, SortOrder.DESC)


def test_comment_body_must_not_be_blank() -> None:
    """Whitespace-only comments are rejected."""
    with pytest.raises(ValidationError):
        CommentCreate.model_validate({"body": "   "})


def test_member_read_from_orm() -> None:
    """Membership rows serialize with their role."""
    membership = Membership(
        id=1,
        project_id=2,
        user_id=3,
        role=MembershipRole.OWNER,
        created_at=datetime.now(timezone(timedelta(hours=3))),
    )
    member = MemberRead.model_validate(membership)
    assert member.model_dump(mode="json")["role"] == "owner"


def test_page_serializes_items() -> None:
    """Generic page wraps typed items with paging metadata."""
    page = Page[int](items=[1, 2], total=5, limit=2, offset=0)
    assert page.model_dump() == {"items": [1, 2], "total": 5, "limit": 2, "offset": 0}
