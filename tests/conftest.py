"""Shared pytest fixtures."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    """Return a fresh application instance.

    Returns
    -------
    FastAPI
        Application isolated from other tests.
    """
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Yield an HTTP client bound to the application in-process.

    Parameters
    ----------
    app : FastAPI
        Application under test.

    Yields
    ------
    AsyncClient
        Client sending requests through ``ASGITransport``.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
