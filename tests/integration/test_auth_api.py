"""Integration tests for ``/api/v1/auth``."""

from typing import Any

import pytest
from httpx import AsyncClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ANN = {"email": "Ann@Example.com", "password": "password123", "full_name": "Ann"}


async def test_register_returns_201_without_secrets(client: AsyncClient) -> None:
    """The created user is returned with normalized email and no password data."""
    response = await client.post(REGISTER, json=ANN)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "full_name", "created_at", "updated_at"}
    assert body["email"] == "ann@example.com"
    assert "password123" not in response.text


async def test_register_duplicate_email_returns_409(client: AsyncClient) -> None:
    """An email registered in another case is a conflict."""
    await client.post(REGISTER, json=ANN)
    response = await client.post(REGISTER, json={**ANN, "email": "ANN@example.com"})
    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {**ANN, "email": "not-an-email"},
        {**ANN, "password": "short"},
        {**ANN, "full_name": "   "},
        {**ANN, "role": "admin"},
        {"email": "ann@example.com", "password": "password123"},
    ],
    ids=["bad-email", "short-password", "blank-name", "extra-field", "missing-name"],
)
async def test_register_invalid_payload_returns_422(
    client: AsyncClient,
    payload: dict[str, Any],
) -> None:
    """Schema violations are rejected before reaching the service."""
    assert (await client.post(REGISTER, json=payload)).status_code == 422


@pytest.mark.parametrize(
    ("url", "payload"),
    [
        (REGISTER, {**ANN, "password": "s3cr"}),
        (LOGIN, ["ann@example.com", "Secret-Pass-1"]),
        (LOGIN, {"email": "ann@example.com", "password": "Secret-Pass-1" * 20}),
    ],
    ids=["register-short-password", "login-non-object-body", "login-too-long-password"],
)
async def test_validation_error_does_not_echo_password(
    client: AsyncClient,
    url: str,
    payload: Any,
) -> None:
    """422 responses describe the error without returning the submitted values."""
    response = await client.post(url, json=payload)
    assert response.status_code == 422
    assert all("input" not in error for error in response.json()["detail"])
    assert "s3cr" not in response.text
    assert "Secret-Pass-1" not in response.text


async def test_login_returns_bearer_token(client: AsyncClient) -> None:
    """Valid credentials (any email case) give a bearer token."""
    await client.post(REGISTER, json=ANN)
    response = await client.post(
        LOGIN, json={"email": "ANN@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"  # noqa: S105 - token scheme, not a secret
    assert body["access_token"]


@pytest.mark.parametrize(
    "credentials",
    [
        {"email": "ann@example.com", "password": "wrong-password"},
        {"email": "nobody@example.com", "password": "password123"},
    ],
    ids=["wrong-password", "unknown-email"],
)
async def test_login_bad_credentials_returns_401(
    client: AsyncClient,
    credentials: dict[str, str],
) -> None:
    """Both failure causes give the same 401 response."""
    await client.post(REGISTER, json=ANN)
    response = await client.post(LOGIN, json=credentials)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


async def test_login_missing_password_returns_422(client: AsyncClient) -> None:
    """An incomplete body is invalid data."""
    assert (await client.post(LOGIN, json={"email": "ann@example.com"})).status_code == 422
