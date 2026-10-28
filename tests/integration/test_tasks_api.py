"""Integration tests for ``/api/v1/projects/{project_id}/tasks`` and ``/api/v1/tasks/{task_id}``."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from app._detail.constants import TASK_TITLE_MAX_LENGTH
from tests.integration.api_helpers import get_user_id, make_team

PROJECTS = "/api/v1/projects"
TASKS = "/api/v1/tasks"
TASK_FIELDS = {
    "id",
    "project_id",
    "title",
    "description",
    "status",
    "priority",
    "assignee_id",
    "due_at",
    "created_at",
    "updated_at",
}


def without_timestamps(task: dict[str, Any]) -> dict[str, Any]:
    """Drop ``created_at`` and ``updated_at`` from a task body.

    SQLite returns stored timestamps without a timezone, so their text differs
    between the create response and later reads.

    Parameters
    ----------
    task : dict[str, Any]
        Task body.

    Returns
    -------
    dict[str, Any]
        The body without timestamp fields.
    """
    return {key: value for key, value in task.items() if key not in {"created_at", "updated_at"}}


def tasks_url(project_id: int) -> str:
    """Return the tasks collection URL of a project.

    Parameters
    ----------
    project_id : int
        Project identifier.

    Returns
    -------
    str
        Tasks collection URL.
    """
    return f"{PROJECTS}/{project_id}/tasks"


async def create_task(
    client: AsyncClient,
    project_id: int,
    headers: dict[str, str],
    **fields: Any,
) -> dict[str, Any]:
    """Create a task through the API and return its body.

    Parameters
    ----------
    client : AsyncClient
        Test client.
    project_id : int
        Project identifier.
    headers : dict[str, str]
        ``Authorization`` header of a project member.
    **fields : Any
        Extra task fields; ``title`` defaults to ``"Write docs"``.

    Returns
    -------
    dict[str, Any]
        Created task.
    """
    response = await client.post(
        tasks_url(project_id), headers=headers, json={"title": "Write docs", **fields}
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", f"{PROJECTS}/1/tasks"),
        ("GET", f"{PROJECTS}/1/tasks"),
        ("GET", f"{TASKS}/1"),
        ("PATCH", f"{TASKS}/1"),
        ("DELETE", f"{TASKS}/1"),
    ],
)
async def test_tasks_require_token(client: AsyncClient, method: str, path: str) -> None:
    """Every task endpoint answers 401 without a bearer token."""
    response = await client.request(method, path, json={"title": "X"})
    assert response.status_code == 401


async def test_create_by_member_with_defaults(client: AsyncClient) -> None:
    """A member creates a task; defaults are applied and no extra fields leak."""
    project_id, _, member, _ = await make_team(client)
    body = await create_task(client, project_id, member, title="  Write docs  ")
    assert set(body) == TASK_FIELDS
    assert (body["project_id"], body["title"], body["description"]) == (
        project_id,
        "Write docs",
        None,
    )
    assert (body["status"], body["priority"], body["assignee_id"], body["due_at"]) == (
        "todo",
        "medium",
        None,
        None,
    )


async def test_create_with_assignee_and_due_at_in_utc(client: AsyncClient) -> None:
    """A member can be the assignee; ``due_at`` with an offset is returned in UTC."""
    project_id, owner, member, _ = await make_team(client)
    member_id = await get_user_id(client, member)
    body = await create_task(
        client,
        project_id,
        owner,
        status="in_progress",
        priority="high",
        assignee_id=member_id,
        due_at="2030-01-01T15:00:00+03:00",
    )
    assert (body["status"], body["priority"], body["assignee_id"]) == (
        "in_progress",
        "high",
        member_id,
    )
    assert body["due_at"] in {"2030-01-01T12:00:00Z", "2030-01-01T12:00:00+00:00"}


async def test_create_hidden_from_outsider_and_missing_project(client: AsyncClient) -> None:
    """Non-members and missing projects give 404."""
    project_id, owner, _, outsider = await make_team(client)
    for headers, target in ((outsider, project_id), (owner, project_id + 1)):
        response = await client.post(tasks_url(target), headers=headers, json={"title": "X"})
        assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": ""},
        {"title": "   "},
        {"title": "x" * (TASK_TITLE_MAX_LENGTH + 1)},
        {"title": "X", "status": "blocked"},
        {"title": "X", "priority": "urgent"},
        {"title": "X", "due_at": "2030-01-01T12:00:00"},
        {"title": "X", "assignee_id": 0},
        {"title": "X", "owner_id": 1},
    ],
)
async def test_create_rejects_invalid_payload(client: AsyncClient, payload: dict[str, Any]) -> None:
    """Invalid fields, a naive ``due_at`` and unknown fields give 422."""
    project_id, owner, _, _ = await make_team(client)
    response = await client.post(tasks_url(project_id), headers=owner, json=payload)
    assert response.status_code == 422


async def test_create_rejects_non_member_assignee(client: AsyncClient) -> None:
    """An assignee outside the project gives 422."""
    project_id, owner, _, outsider = await make_team(client)
    outsider_id = await get_user_id(client, outsider)
    response = await client.post(
        tasks_url(project_id), headers=owner, json={"title": "X", "assignee_id": outsider_id}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Assignee must be a project member"


async def test_get_for_members_only(client: AsyncClient) -> None:
    """Owner and member read the task; outsiders and missing ids get 404."""
    project_id, owner, member, outsider = await make_team(client)
    task = await create_task(client, project_id, owner)
    for headers in (owner, member):
        response = await client.get(f"{TASKS}/{task['id']}", headers=headers)
        assert response.status_code == 200
        assert without_timestamps(response.json()) == without_timestamps(task)
    assert (await client.get(f"{TASKS}/{task['id']}", headers=outsider)).status_code == 404
    assert (await client.get(f"{TASKS}/{task['id'] + 1}", headers=owner)).status_code == 404


async def test_update_by_member(client: AsyncClient) -> None:
    """A member changes the owner's task; omitted fields stay unchanged."""
    project_id, owner, member, _ = await make_team(client)
    member_id = await get_user_id(client, member)
    task = await create_task(client, project_id, owner, description="API")
    response = await client.patch(
        f"{TASKS}/{task['id']}",
        headers=member,
        json={"status": "done", "assignee_id": member_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["title"], body["description"]) == ("Write docs", "API")
    assert (body["status"], body["assignee_id"]) == ("done", member_id)


async def test_update_clears_nullable_fields(client: AsyncClient) -> None:
    """Explicit ``null`` clears ``description``, ``assignee_id`` and ``due_at``."""
    project_id, owner, _, _ = await make_team(client)
    owner_id = await get_user_id(client, owner)
    task = await create_task(
        client,
        project_id,
        owner,
        description="API",
        assignee_id=owner_id,
        due_at="2030-01-01T12:00:00Z",
    )
    response = await client.patch(
        f"{TASKS}/{task['id']}",
        headers=owner,
        json={"description": None, "assignee_id": None, "due_at": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["description"], body["assignee_id"], body["due_at"]) == (None, None, None)


@pytest.mark.parametrize(
    "payload",
    [
        {"title": None},
        {"status": None},
        {"title": ""},
        {"priority": "urgent"},
        {"due_at": "2030-01-01T12:00:00"},
        {"project_id": 2},
    ],
)
async def test_update_rejects_invalid_payload(client: AsyncClient, payload: dict[str, Any]) -> None:
    """``null`` for required fields, invalid values and unknown fields give 422."""
    project_id, owner, _, _ = await make_team(client)
    task = await create_task(client, project_id, owner)
    response = await client.patch(f"{TASKS}/{task['id']}", headers=owner, json=payload)
    assert response.status_code == 422


async def test_update_rejects_non_member_assignee_and_outsider(client: AsyncClient) -> None:
    """Reassigning to a non-member gives 422; an outsider editing gives 404."""
    project_id, owner, _, outsider = await make_team(client)
    outsider_id = await get_user_id(client, outsider)
    task = await create_task(client, project_id, owner)
    url = f"{TASKS}/{task['id']}"
    response = await client.patch(url, headers=owner, json={"assignee_id": outsider_id})
    assert response.status_code == 422
    assert (await client.patch(url, headers=outsider, json={"title": "Y"})).status_code == 404
    stored = (await client.get(url, headers=owner)).json()
    assert without_timestamps(stored) == without_timestamps(task)


async def test_delete_by_member(client: AsyncClient) -> None:
    """A member deletes the owner's task; it is gone afterwards."""
    project_id, owner, member, _ = await make_team(client)
    task = await create_task(client, project_id, owner)
    url = f"{TASKS}/{task['id']}"
    response = await client.delete(url, headers=member)
    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(url, headers=owner)).status_code == 404
    assert (await client.delete(url, headers=owner)).status_code == 404


async def test_delete_hidden_from_outsider(client: AsyncClient) -> None:
    """An outsider gets 404 and the task stays."""
    project_id, owner, _, outsider = await make_team(client)
    task = await create_task(client, project_id, owner)
    url = f"{TASKS}/{task['id']}"
    assert (await client.delete(url, headers=outsider)).status_code == 404
    assert (await client.get(url, headers=owner)).status_code == 200


async def test_removed_member_loses_access_and_assignment(client: AsyncClient) -> None:
    """After removal the former member gets 404 and their task becomes unassigned."""
    project_id, owner, member, _ = await make_team(client)
    member_id = await get_user_id(client, member)
    task = await create_task(client, project_id, member, assignee_id=member_id)
    url = f"{TASKS}/{task['id']}"
    response = await client.delete(f"{PROJECTS}/{project_id}/members/{member_id}", headers=owner)
    assert response.status_code == 204
    assert (await client.get(url, headers=member)).status_code == 404
    assert (await client.get(url, headers=owner)).json()["assignee_id"] is None


async def test_project_delete_removes_tasks(client: AsyncClient) -> None:
    """Deleting the project deletes its tasks."""
    project_id, owner, _, _ = await make_team(client)
    task = await create_task(client, project_id, owner)
    assert (await client.delete(f"{PROJECTS}/{project_id}", headers=owner)).status_code == 204
    assert (await client.get(f"{TASKS}/{task['id']}", headers=owner)).status_code == 404


async def list_titles(
    client: AsyncClient, project_id: int, headers: dict[str, str], **params: Any
) -> list[str]:
    """List a project's tasks and return their titles.

    Parameters
    ----------
    client : AsyncClient
        Test client.
    project_id : int
        Project identifier.
    headers : dict[str, str]
        ``Authorization`` header of a project member.
    **params : Any
        Query parameters.

    Returns
    -------
    list[str]
        Titles in listed order.
    """
    response = await client.get(tasks_url(project_id), headers=headers, params=params)
    assert response.status_code == 200
    return [task["title"] for task in response.json()["items"]]


async def test_list_by_member_with_pagination(client: AsyncClient) -> None:
    """Members get a newest-first page with ``total``, ``limit`` and ``offset``."""
    project_id, owner, member, _ = await make_team(client)
    for title in ("first", "second", "third"):
        await create_task(client, project_id, owner, title=title)
    response = await client.get(tasks_url(project_id), headers=member)
    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["limit"], body["offset"]) == (3, 20, 0)
    assert [task["title"] for task in body["items"]] == ["third", "second", "first"]
    assert set(body["items"][0]) == TASK_FIELDS
    response = await client.get(
        tasks_url(project_id), headers=member, params={"limit": 1, "offset": 1}
    )
    assert response.json() | {"items": None} == {
        "items": None,
        "total": 3,
        "limit": 1,
        "offset": 1,
    }
    assert [task["title"] for task in response.json()["items"]] == ["second"]


async def test_list_filters(client: AsyncClient) -> None:
    """``status``, ``priority``, ``assignee_id`` and ``overdue`` narrow the list."""
    project_id, owner, member, _ = await make_team(client)
    member_id = await get_user_id(client, member)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    await create_task(client, project_id, owner, title="late", due_at=past, assignee_id=member_id)
    await create_task(client, project_id, owner, title="done-late", due_at=past, status="done")
    await create_task(client, project_id, owner, title="soon", due_at=future, priority="high")
    await create_task(client, project_id, owner, title="no-due", status="in_progress")
    assert await list_titles(client, project_id, member, status="done") == ["done-late"]
    assert await list_titles(client, project_id, member, priority="high") == ["soon"]
    assert await list_titles(client, project_id, member, assignee_id=member_id) == ["late"]
    assert await list_titles(client, project_id, member, overdue="true") == ["late"]
    assert await list_titles(client, project_id, member, overdue="false") == [
        "no-due",
        "soon",
        "done-late",
    ]
    assert await list_titles(client, project_id, member, status="todo", priority="high") == ["soon"]


async def test_list_sorting(client: AsyncClient) -> None:
    """``sort`` and ``order`` change the order; the default is newest first."""
    project_id, owner, _, _ = await make_team(client)
    for title in ("first", "second", "third"):
        await create_task(client, project_id, owner, title=title)
    assert await list_titles(client, project_id, owner, order="asc") == ["first", "second", "third"]
    assert await list_titles(client, project_id, owner, sort="id", order="desc") == [
        "third",
        "second",
        "first",
    ]


async def test_list_hidden_from_outsider_and_missing_project(client: AsyncClient) -> None:
    """Non-members and missing projects give 404; other teams' tasks never leak."""
    project_id, owner, _, outsider = await make_team(client)
    await create_task(client, project_id, owner)
    for target in (project_id, project_id + 100):
        response = await client.get(tasks_url(target), headers=outsider)
        assert response.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"status": "unknown"},
        {"priority": "urgent"},
        {"assignee_id": 0},
        {"overdue": "maybe"},
        {"sort": "title"},
        {"order": "up"},
    ],
)
async def test_list_rejects_invalid_query(client: AsyncClient, params: dict[str, Any]) -> None:
    """Out-of-range pagination and unknown filter or sort values give 422."""
    project_id, owner, _, _ = await make_team(client)
    response = await client.get(tasks_url(project_id), headers=owner, params=params)
    assert response.status_code == 422
