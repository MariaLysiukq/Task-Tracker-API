"""Integration tests for ``/api/v1/projects``."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MembershipRole
from app.repositories import membership as membership_repo
from tests.integration.api_helpers import register_and_login

PROJECTS = "/api/v1/projects"
ME = "/api/v1/users/me"


async def make_team(
    client: AsyncClient,
    db_session: AsyncSession,
) -> tuple[int, dict[str, str], dict[str, str], dict[str, str]]:
    """Create a project via the API with an owner, a member and an outsider.

    The member is added directly in the database until the members endpoint exists.

    Parameters
    ----------
    client : AsyncClient
        Test client.
    db_session : AsyncSession
        Test session.

    Returns
    -------
    tuple[int, dict[str, str], dict[str, str], dict[str, str]]
        Project id and auth headers of the owner, member and outsider.
    """
    owner = await register_and_login(client, "owner@example.com")
    member = await register_and_login(client, "member@example.com")
    outsider = await register_and_login(client, "outsider@example.com")
    project_id = (await client.post(PROJECTS, headers=owner, json={"name": "Alpha"})).json()["id"]
    member_id = (await client.get(ME, headers=member)).json()["id"]
    await membership_repo.create(
        db_session, project_id=project_id, user_id=member_id, role=MembershipRole.MEMBER
    )
    await db_session.commit()
    return project_id, owner, member, outsider


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", PROJECTS),
        ("GET", PROJECTS),
        ("GET", f"{PROJECTS}/1"),
        ("PATCH", f"{PROJECTS}/1"),
        ("DELETE", f"{PROJECTS}/1"),
    ],
)
async def test_projects_require_token(client: AsyncClient, method: str, path: str) -> None:
    """Every project endpoint answers 401 without a bearer token."""
    response = await client.request(method, path, json={"name": "Alpha"})
    assert response.status_code == 401


async def test_create_returns_201_with_owner(client: AsyncClient) -> None:
    """The creator becomes the owner and the project is listed for them."""
    headers = await register_and_login(client)
    user_id = (await client.get(ME, headers=headers)).json()["id"]
    response = await client.post(
        PROJECTS, headers=headers, json={"name": "  Alpha  ", "description": "Docs"}
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "name", "description", "owner_id", "created_at", "updated_at"}
    assert body["name"] == "Alpha"
    assert body["owner_id"] == user_id
    assert (await client.get(f"{PROJECTS}/{body['id']}", headers=headers)).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [{"name": "   "}, {"name": "x" * 101}, {}, {"name": "Alpha", "owner_id": 5}],
    ids=["blank-name", "long-name", "missing-name", "extra-field"],
)
async def test_create_invalid_payload_returns_422(
    client: AsyncClient,
    payload: dict[str, Any],
) -> None:
    """Schema violations are rejected."""
    headers = await register_and_login(client)
    assert (await client.post(PROJECTS, headers=headers, json=payload)).status_code == 422


async def test_list_shows_only_own_projects(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Members see the project; outsiders get an empty page."""
    project_id, owner, member, outsider = await make_team(client, db_session)
    for headers in (owner, member):
        body = (await client.get(PROJECTS, headers=headers)).json()
        assert [item["id"] for item in body["items"]] == [project_id]
        assert body["total"] == 1
    body = (await client.get(PROJECTS, headers=outsider)).json()
    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


async def test_list_paginates_newest_first(client: AsyncClient) -> None:
    """``limit``/``offset`` slice a newest-first list; the total stays complete."""
    headers = await register_and_login(client)
    for name in ("A", "B", "C"):
        await client.post(PROJECTS, headers=headers, json={"name": name})
    response = await client.get(PROJECTS, headers=headers, params={"limit": 2, "offset": 1})
    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body["items"]] == ["B", "A"]
    assert (body["total"], body["limit"], body["offset"]) == (3, 2, 1)


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "many"}],
    ids=["limit-zero", "limit-too-big", "negative-offset", "not-a-number"],
)
async def test_list_invalid_pagination_returns_422(
    client: AsyncClient,
    params: dict[str, Any],
) -> None:
    """Out-of-range pagination parameters are invalid data."""
    headers = await register_and_login(client)
    assert (await client.get(PROJECTS, headers=headers, params=params)).status_code == 422


async def test_read_by_members_only(client: AsyncClient, db_session: AsyncSession) -> None:
    """Members read the project; outsiders and missing ids get 404."""
    project_id, owner, member, outsider = await make_team(client, db_session)
    url = f"{PROJECTS}/{project_id}"
    assert (await client.get(url, headers=owner)).status_code == 200
    assert (await client.get(url, headers=member)).json()["name"] == "Alpha"
    assert (await client.get(url, headers=outsider)).status_code == 404
    assert (await client.get(f"{PROJECTS}/{project_id + 1}", headers=owner)).status_code == 404


async def test_update_by_owner(client: AsyncClient, db_session: AsyncSession) -> None:
    """The owner changes sent fields; the description can be cleared."""
    project_id, owner, _, _ = await make_team(client, db_session)
    response = await client.patch(
        f"{PROJECTS}/{project_id}", headers=owner, json={"name": "Beta", "description": None}
    )
    assert response.status_code == 200
    assert (response.json()["name"], response.json()["description"]) == ("Beta", None)


@pytest.mark.parametrize(
    ("who", "expected_status"),
    [("member", 403), ("outsider", 404)],
)
async def test_update_and_delete_by_non_owner(
    client: AsyncClient,
    db_session: AsyncSession,
    who: str,
    expected_status: int,
) -> None:
    """Members get 403, outsiders 404; the project is unchanged."""
    project_id, owner, member, outsider = await make_team(client, db_session)
    headers = member if who == "member" else outsider
    url = f"{PROJECTS}/{project_id}"
    patch = await client.patch(url, headers=headers, json={"name": "Hacked"})
    assert patch.status_code == expected_status
    assert (await client.delete(url, headers=headers)).status_code == expected_status
    assert (await client.get(url, headers=owner)).json()["name"] == "Alpha"


@pytest.mark.parametrize(
    "payload",
    [{"name": None}, {"name": ""}, {"owner_id": 2}],
    ids=["null-name", "empty-name", "extra-field"],
)
async def test_update_invalid_payload_returns_422(
    client: AsyncClient,
    payload: dict[str, Any],
) -> None:
    """Schema violations are rejected."""
    headers = await register_and_login(client)
    project_id = (await client.post(PROJECTS, headers=headers, json={"name": "A"})).json()["id"]
    response = await client.patch(f"{PROJECTS}/{project_id}", headers=headers, json=payload)
    assert response.status_code == 422


async def test_delete_by_owner_unblocks_account_deletion(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """After 204 the project is gone for everyone and the owner can delete the account."""
    project_id, owner, member, _ = await make_team(client, db_session)
    url = f"{PROJECTS}/{project_id}"
    assert (await client.delete(ME, headers=owner)).status_code == 409
    response = await client.delete(url, headers=owner)
    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(url, headers=owner)).status_code == 404
    assert (await client.get(PROJECTS, headers=member)).json()["total"] == 0
    assert (await client.delete(ME, headers=owner)).status_code == 204
