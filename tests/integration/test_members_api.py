"""Integration tests for ``/api/v1/projects/{project_id}/members``."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task
from tests.integration.api_helpers import get_user_id, make_team, register_and_login

PROJECTS = "/api/v1/projects"


def members_url(project_id: int) -> str:
    """Return the members collection URL of a project.

    Parameters
    ----------
    project_id : int
        Project identifier.

    Returns
    -------
    str
        Members collection URL.
    """
    return f"{PROJECTS}/{project_id}/members"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", f"{PROJECTS}/1/members"),
        ("POST", f"{PROJECTS}/1/members"),
        ("DELETE", f"{PROJECTS}/1/members/2"),
    ],
)
async def test_members_require_token(client: AsyncClient, method: str, path: str) -> None:
    """Every member endpoint answers 401 without a bearer token."""
    response = await client.request(method, path, json={"user_id": 2})
    assert response.status_code == 401


async def test_list_for_members_newest_first(client: AsyncClient) -> None:
    """Owner and member see both memberships with roles, newest first."""
    project_id, owner, member, _ = await make_team(client)
    owner_id = await get_user_id(client, owner)
    member_id = await get_user_id(client, member)
    for headers in (owner, member):
        response = await client.get(members_url(project_id), headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert [(item["user_id"], item["role"]) for item in body["items"]] == [
            (member_id, "member"),
            (owner_id, "owner"),
        ]
        assert set(body["items"][0]) == {"project_id", "user_id", "role", "created_at"}
        assert (body["total"], body["limit"], body["offset"]) == (2, 20, 0)
    response = await client.get(members_url(project_id), headers=owner, params={"limit": 1})
    assert [item["user_id"] for item in response.json()["items"]] == [member_id]


async def test_list_hidden_from_outsider_and_missing_project(client: AsyncClient) -> None:
    """Non-members and missing projects give 404; bad pagination gives 422."""
    project_id, owner, _, outsider = await make_team(client)
    assert (await client.get(members_url(project_id), headers=outsider)).status_code == 404
    assert (await client.get(members_url(project_id + 1), headers=owner)).status_code == 404
    response = await client.get(members_url(project_id), headers=owner, params={"limit": 0})
    assert response.status_code == 422


async def test_add_by_owner_grants_access(client: AsyncClient) -> None:
    """The added user gets the ``member`` role and can read the project."""
    project_id, owner, _, outsider = await make_team(client)
    outsider_id = await get_user_id(client, outsider)
    response = await client.post(
        members_url(project_id), headers=owner, json={"user_id": outsider_id}
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == outsider_id
    assert response.json()["role"] == "member"
    assert (await client.get(f"{PROJECTS}/{project_id}", headers=outsider)).status_code == 200


async def test_add_by_non_owner_is_rejected(client: AsyncClient) -> None:
    """A member gets 403, an outsider 404."""
    project_id, _, member, outsider = await make_team(client)
    newcomer = await register_and_login(client, "new@example.com")
    payload = {"user_id": await get_user_id(client, newcomer)}
    url = members_url(project_id)
    assert (await client.post(url, headers=member, json=payload)).status_code == 403
    assert (await client.post(url, headers=outsider, json=payload)).status_code == 404


async def test_add_unknown_user_or_duplicate(client: AsyncClient) -> None:
    """An unknown user gives 404; an existing member or the owner gives 409."""
    project_id, owner, member, _ = await make_team(client)
    url = members_url(project_id)
    assert (await client.post(url, headers=owner, json={"user_id": 999})).status_code == 404
    for headers in (member, owner):
        payload = {"user_id": await get_user_id(client, headers)}
        assert (await client.post(url, headers=owner, json=payload)).status_code == 409


@pytest.mark.parametrize(
    "payload",
    [{}, {"user_id": 0}, {"user_id": "bob"}, {"user_id": 3, "role": "owner"}],
    ids=["missing", "zero", "not-a-number", "extra-field"],
)
async def test_add_invalid_payload_returns_422(
    client: AsyncClient,
    payload: dict[str, Any],
) -> None:
    """Schema violations are rejected."""
    project_id, owner, _, _ = await make_team(client)
    response = await client.post(members_url(project_id), headers=owner, json=payload)
    assert response.status_code == 422


async def test_remove_unassigns_tasks_and_revokes_access(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """After 204 the member loses access and their tasks lose the assignee."""
    project_id, owner, member, _ = await make_team(client)
    member_id = await get_user_id(client, member)
    task = Task(project_id=project_id, title="Write docs", assignee_id=member_id)
    db_session.add(task)
    await db_session.commit()
    response = await client.delete(f"{members_url(project_id)}/{member_id}", headers=owner)
    assert response.status_code == 204
    assert response.content == b""
    await db_session.refresh(task)
    assert task.assignee_id is None
    assert (await client.get(f"{PROJECTS}/{project_id}", headers=member)).status_code == 404
    assert (await client.get(members_url(project_id), headers=owner)).json()["total"] == 1


async def test_remove_owner_or_non_member(client: AsyncClient) -> None:
    """Removing the owner gives 409; removing a non-member gives 404."""
    project_id, owner, _, outsider = await make_team(client)
    url = members_url(project_id)
    owner_id = await get_user_id(client, owner)
    outsider_id = await get_user_id(client, outsider)
    assert (await client.delete(f"{url}/{owner_id}", headers=owner)).status_code == 409
    assert (await client.delete(f"{url}/{outsider_id}", headers=owner)).status_code == 404


async def test_remove_by_non_owner_is_rejected(client: AsyncClient) -> None:
    """A member gets 403, an outsider 404; the membership stays."""
    project_id, owner, member, outsider = await make_team(client)
    url = f"{members_url(project_id)}/{await get_user_id(client, member)}"
    assert (await client.delete(url, headers=member)).status_code == 403
    assert (await client.delete(url, headers=outsider)).status_code == 404
    assert (await client.get(members_url(project_id), headers=owner)).json()["total"] == 2
