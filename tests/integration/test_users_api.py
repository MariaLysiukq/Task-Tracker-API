"""Integration tests for ``/api/v1/users/me``."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project
from tests.integration.api_helpers import register_and_login

ME = "/api/v1/users/me"


async def test_read_me(client: AsyncClient) -> None:
    """The token owner's profile is returned."""
    headers = await register_and_login(client)
    response = await client.get(ME, headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "ann@example.com"
    assert "hashed_password" not in response.json()


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer not-a-token"}, {"Authorization": "Basic YTpi"}],
    ids=["no-header", "bad-token", "wrong-scheme"],
)
async def test_me_requires_valid_token(
    client: AsyncClient,
    method: str,
    headers: dict[str, str],
) -> None:
    """Every ``/users/me`` method answers 401 without a valid bearer token."""
    response = await client.request(method, ME, headers=headers, json={"full_name": "X"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_update_me(client: AsyncClient) -> None:
    """Only sent fields change; a new password works for the next login."""
    headers = await register_and_login(client)
    response = await client.patch(
        ME,
        headers=headers,
        json={"full_name": "Anna", "password": "new-password", "current_password": "password123"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Anna"
    assert response.json()["email"] == "ann@example.com"
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ann@example.com", "password": "new-password"},
    )
    assert login.status_code == 200
    assert "password" not in response.text


async def test_update_name_needs_no_current_password(client: AsyncClient) -> None:
    """Changing only the full name works without ``current_password``."""
    headers = await register_and_login(client)
    response = await client.patch(ME, headers=headers, json={"full_name": "Anna"})
    assert (response.status_code, response.json()["full_name"]) == (200, "Anna")


@pytest.mark.parametrize(
    "payload",
    [{"password": "new-password"}, {"email": "new@example.com"}],
    ids=["password", "email"],
)
async def test_sensitive_change_without_current_password_returns_422(
    client: AsyncClient,
    payload: dict[str, str],
) -> None:
    """Email or password changes are rejected without ``current_password``."""
    headers = await register_and_login(client)
    response = await client.patch(ME, headers=headers, json=payload)
    assert response.status_code == 422
    assert "current_password" in response.text


async def test_wrong_current_password_returns_403(client: AsyncClient) -> None:
    """A wrong current password is refused and the old password keeps working."""
    headers = await register_and_login(client)
    response = await client.patch(
        ME,
        headers=headers,
        json={"password": "new-password", "current_password": "wrong-password"},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Current password is incorrect"}
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ann@example.com", "password": "password123"},
    )
    assert login.status_code == 200


async def test_update_me_taken_email_returns_409(client: AsyncClient) -> None:
    """Another user's email is a conflict."""
    headers = await register_and_login(client)
    await register_and_login(client, "bob@example.com")
    payload = {"email": "BOB@example.com", "current_password": "password123"}
    response = await client.patch(ME, headers=headers, json=payload)
    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"full_name": None},
        {"email": "not-an-email", "current_password": "password123"},
        {"password": "short", "current_password": "password123"},
        {"id": 5},
        {"full_name": "Anna", "current_password": ""},
    ],
    ids=["null-name", "bad-email", "short-password", "extra-field", "empty-current-password"],
)
async def test_update_me_invalid_payload_returns_422(
    client: AsyncClient,
    payload: dict[str, Any],
) -> None:
    """Schema violations are rejected."""
    headers = await register_and_login(client)
    assert (await client.patch(ME, headers=headers, json=payload)).status_code == 422


async def test_delete_me(client: AsyncClient) -> None:
    """After deletion the token no longer authenticates."""
    headers = await register_and_login(client)
    response = await client.delete(ME, headers=headers)
    assert response.status_code == 204
    assert response.content == b""
    assert (await client.get(ME, headers=headers)).status_code == 401


async def test_delete_me_owning_project_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """An owner keeps the account until their projects are deleted."""
    headers = await register_and_login(client)
    user_id = (await client.get(ME, headers=headers)).json()["id"]
    db_session.add(Project(name="Alpha", owner_id=user_id))
    await db_session.commit()
    assert (await client.delete(ME, headers=headers)).status_code == 409
    assert (await client.get(ME, headers=headers)).status_code == 200
