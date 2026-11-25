"""Integration tests for ``/api/v1/tasks/{task_id}/comments`` and ``/api/v1/comments/{id}``."""

from typing import Any

import pytest
from httpx import AsyncClient

from app._detail.constants import COMMENT_BODY_MAX_LENGTH
from tests.integration.api_helpers import get_user_id, make_team

PROJECTS = "/api/v1/projects"
TASKS = "/api/v1/tasks"
COMMENTS = "/api/v1/comments"
COMMENT_FIELDS = {"id", "task_id", "author_id", "body", "created_at", "updated_at"}


async def make_comment(
    client: AsyncClient,
) -> tuple[dict[str, Any], int, int, dict[str, str], dict[str, str], dict[str, str]]:
    """Create a team, a task and a comment written by the member.

    Parameters
    ----------
    client : AsyncClient
        Test client.

    Returns
    -------
    tuple[dict[str, Any], int, int, dict[str, str], dict[str, str], dict[str, str]]
        Comment body, task id, project id and headers of the owner, member and outsider.
    """
    project_id, owner, member, outsider = await make_team(client)
    task = await client.post(f"{PROJECTS}/{project_id}/tasks", headers=owner, json={"title": "X"})
    task_id = int(task.json()["id"])
    response = await client.post(f"{TASKS}/{task_id}/comments", headers=member, json={"body": "Hi"})
    assert response.status_code == 201
    return response.json(), task_id, project_id, owner, member, outsider


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", f"{TASKS}/1/comments"),
        ("GET", f"{TASKS}/1/comments"),
        ("PATCH", f"{COMMENTS}/1"),
        ("DELETE", f"{COMMENTS}/1"),
    ],
)
async def test_comments_require_token(client: AsyncClient, method: str, path: str) -> None:
    """Every comment endpoint answers 401 without a bearer token."""
    response = await client.request(method, path, json={"body": "X"})
    assert response.status_code == 401


async def test_create_by_member(client: AsyncClient) -> None:
    """A member comments; the author is the caller and only public fields are returned."""
    comment, task_id, _, _, member, _ = await make_comment(client)
    assert set(comment) == COMMENT_FIELDS
    assert (comment["task_id"], comment["author_id"], comment["body"]) == (
        task_id,
        await get_user_id(client, member),
        "Hi",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"body": ""},
        {"body": "   "},
        {"body": "x" * (COMMENT_BODY_MAX_LENGTH + 1)},
        {"body": "X", "author_id": 1},
    ],
)
async def test_create_rejects_invalid_payload(client: AsyncClient, payload: dict[str, Any]) -> None:
    """Empty, too long or unknown fields give 422."""
    _, task_id, _, owner, _, _ = await make_comment(client)
    response = await client.post(f"{TASKS}/{task_id}/comments", headers=owner, json=payload)
    assert response.status_code == 422


async def test_list_by_member_with_pagination(client: AsyncClient) -> None:
    """Members get a newest-first page with ``total``, ``limit`` and ``offset``."""
    _, task_id, _, owner, member, _ = await make_comment(client)
    await client.post(f"{TASKS}/{task_id}/comments", headers=owner, json={"body": "Reply"})
    response = await client.get(f"{TASKS}/{task_id}/comments", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert ([item["body"] for item in body["items"]], body["total"]) == (["Reply", "Hi"], 2)
    response = await client.get(
        f"{TASKS}/{task_id}/comments", headers=owner, params={"limit": 1, "offset": 1}
    )
    body = response.json()
    assert ([item["body"] for item in body["items"]], body["limit"], body["offset"]) == (
        ["Hi"],
        1,
        1,
    )


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
async def test_list_rejects_invalid_pagination(client: AsyncClient, params: dict[str, Any]) -> None:
    """Out-of-range pagination gives 422."""
    _, task_id, _, owner, _, _ = await make_comment(client)
    response = await client.get(f"{TASKS}/{task_id}/comments", headers=owner, params=params)
    assert response.status_code == 422


async def test_create_and_list_hidden_from_outsider(client: AsyncClient) -> None:
    """Non-members and missing tasks give 404."""
    _, task_id, _, _, _, outsider = await make_comment(client)
    for target in (task_id, task_id + 100):
        url = f"{TASKS}/{target}/comments"
        assert (await client.get(url, headers=outsider)).status_code == 404
        assert (await client.post(url, headers=outsider, json={"body": "X"})).status_code == 404


async def test_update_and_delete_by_author(client: AsyncClient) -> None:
    """The author edits (200) and deletes (204) their comment."""
    comment, task_id, _, _, member, _ = await make_comment(client)
    url = f"{COMMENTS}/{comment['id']}"
    response = await client.patch(url, headers=member, json={"body": "  Edited  "})
    assert response.status_code == 200
    assert response.json()["body"] == "Edited"
    assert (await client.delete(url, headers=member)).status_code == 204
    listed = await client.get(f"{TASKS}/{task_id}/comments", headers=member)
    assert listed.json()["total"] == 0


@pytest.mark.parametrize("payload", [{}, {"body": ""}, {"body": None}, {"task_id": 1, "body": "X"}])
async def test_update_rejects_invalid_payload(client: AsyncClient, payload: dict[str, Any]) -> None:
    """Missing, empty, null or unknown fields give 422."""
    comment, _, _, _, member, _ = await make_comment(client)
    response = await client.patch(f"{COMMENTS}/{comment['id']}", headers=member, json=payload)
    assert response.status_code == 422


async def test_update_and_delete_by_other_member_forbidden(client: AsyncClient) -> None:
    """Members who are not the author, including the owner, get 403."""
    comment, _, _, owner, _, _ = await make_comment(client)
    url = f"{COMMENTS}/{comment['id']}"
    assert (await client.patch(url, headers=owner, json={"body": "X"})).status_code == 403
    assert (await client.delete(url, headers=owner)).status_code == 403


async def test_update_and_delete_hidden_from_outsider(client: AsyncClient) -> None:
    """Non-members and missing comments give 404."""
    comment, _, _, _, member, outsider = await make_comment(client)
    for headers, comment_id in ((outsider, comment["id"]), (member, comment["id"] + 100)):
        url = f"{COMMENTS}/{comment_id}"
        assert (await client.patch(url, headers=headers, json={"body": "X"})).status_code == 404
        assert (await client.delete(url, headers=headers)).status_code == 404


async def test_removed_author_loses_access(client: AsyncClient) -> None:
    """After removal the author can neither see nor edit their comment."""
    comment, task_id, project_id, owner, member, _ = await make_comment(client)
    member_id = await get_user_id(client, member)
    await client.delete(f"{PROJECTS}/{project_id}/members/{member_id}", headers=owner)
    url = f"{COMMENTS}/{comment['id']}"
    assert (await client.patch(url, headers=member, json={"body": "X"})).status_code == 404
    assert (await client.delete(url, headers=member)).status_code == 404
    response = await client.get(f"{TASKS}/{task_id}/comments", headers=member)
    assert response.status_code == 404


async def test_task_delete_removes_comments(client: AsyncClient) -> None:
    """Deleting the task deletes its comments."""
    comment, task_id, _, owner, member, _ = await make_comment(client)
    assert (await client.delete(f"{TASKS}/{task_id}", headers=owner)).status_code == 204
    response = await client.patch(f"{COMMENTS}/{comment['id']}", headers=member, json={"body": "X"})
    assert response.status_code == 404
