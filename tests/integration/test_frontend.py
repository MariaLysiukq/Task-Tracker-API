"""Integration tests for the web client served at ``/``."""

from httpx import AsyncClient


async def test_index_serves_web_client(client: AsyncClient) -> None:
    """The root path returns the HTML page that calls ``/api/v1``."""
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Task Tracker</title>" in response.text
    assert 'const API = "/api/v1";' in response.text


async def test_index_is_not_in_openapi_schema(client: AsyncClient) -> None:
    """The page route is not documented as an API endpoint."""
    response = await client.get("/openapi.json")
    assert "/" not in response.json()["paths"]


async def test_unknown_path_still_returns_json_404(client: AsyncClient) -> None:
    """Serving the page does not swallow unknown paths."""
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
