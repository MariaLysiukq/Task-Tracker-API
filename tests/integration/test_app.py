"""Integration tests for application wiring and domain error mapping."""

import pytest
from fastapi import FastAPI, Request
from httpx import AsyncClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ConflictError,
    DomainError,
    ForbiddenError,
    InvalidDataError,
    NotFoundError,
    UnauthorizedError,
)
from app.main import create_app, lifespan


async def raise_stored_error(request: Request) -> None:
    """Raise the error stored in ``app.state.error``.

    Parameters
    ----------
    request : Request
        Incoming request giving access to the application state.

    Raises
    ------
    DomainError
        The stored error.
    """
    raise request.app.state.error


@pytest.mark.parametrize(
    ("error_class", "expected_status"),
    [
        (UnauthorizedError, 401),
        (ForbiddenError, 403),
        (NotFoundError, 404),
        (ConflictError, 409),
        (InvalidDataError, 422),
    ],
)
async def test_domain_error_is_mapped_to_status(
    app: FastAPI,
    client: AsyncClient,
    error_class: type[DomainError],
    expected_status: int,
) -> None:
    """Each domain error yields its status code and a ``detail`` body only."""
    app.state.error = error_class("boom")
    app.add_api_route("/raise", raise_stored_error)
    response = await client.get("/raise")
    assert response.status_code == expected_status
    assert response.json() == {"detail": "boom"}


async def test_openapi_is_served(client: AsyncClient) -> None:
    """OpenAPI schema is available for ``/docs``."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Task Tracker API"


@pytest.mark.parametrize(
    ("error_class", "expected_header"),
    [(UnauthorizedError, "Bearer"), (ForbiddenError, None)],
)
async def test_www_authenticate_header_only_on_401(
    app: FastAPI,
    client: AsyncClient,
    error_class: type[DomainError],
    expected_header: str | None,
) -> None:
    """401 responses announce the Bearer scheme; other errors do not."""
    app.state.error = error_class("boom")
    app.add_api_route("/raise", raise_stored_error)
    response = await client.get("/raise")
    assert response.headers.get("www-authenticate") == expected_header


async def test_startup_succeeds_with_valid_settings(settings: Settings) -> None:
    """The lifespan check passes with a valid configuration."""
    async with lifespan(create_app()):
        pass


async def test_startup_fails_with_short_jwt_secret(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server refuses to start when ``JWT_SECRET`` is too short."""
    monkeypatch.setenv("JWT_SECRET", "short")
    get_settings.cache_clear()
    with pytest.raises(ValidationError):
        async with lifespan(create_app()):
            pass
