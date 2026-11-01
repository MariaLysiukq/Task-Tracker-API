"""Integration tests for the web client served at ``/`` and its ``/static`` assets."""

import re

import pytest
from httpx import AsyncClient

from app.api.frontend import CONTENT_SECURITY_POLICY


async def test_index_serves_web_client(client: AsyncClient) -> None:
    """The root path returns the HTML page that loads its own assets."""
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Task Tracker</title>" in response.text
    assert '<script src="/static/app.js" defer></script>' in response.text


async def test_index_sends_strict_page_headers(client: AsyncClient) -> None:
    """The page forbids framing and anything not served by the app itself."""
    response = await client.get("/")
    assert response.headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert "frame-ancestors 'none'" in CONTENT_SECURITY_POLICY
    assert "unsafe-inline" not in CONTENT_SECURITY_POLICY
    assert response.headers["x-frame-options"] == "DENY"


async def test_index_has_no_inline_code_or_external_sources(client: AsyncClient) -> None:
    """Inline scripts, styles and third-party URLs would be blocked by the CSP."""
    html = (await client.get("/")).text
    assert re.search(r"<script(?![^>]*\bsrc=)", html) is None
    assert "<style" not in html
    assert "style=" not in html
    assert re.search(r"""(?:src|href)=["']https?://""", html) is None


@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("/static/app.js", "text/javascript"),
        ("/static/app.css", "text/css"),
        ("/static/fonts/ibm-plex-sans-latin-400-normal.woff2", "font/woff2"),
    ],
)
async def test_static_assets_are_served(client: AsyncClient, path: str, content_type: str) -> None:
    """Script, stylesheet and fonts come from the app with their real types."""
    response = await client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_app_script_calls_api_v1(client: AsyncClient) -> None:
    """The client talks to the versioned API on the same origin."""
    response = await client.get("/static/app.js")
    assert 'const API = "/api/v1";' in response.text


async def test_page_is_not_reachable_without_headers_under_static(client: AsyncClient) -> None:
    """The page is only served at ``/``, so its CSP cannot be bypassed via ``/static``."""
    response = await client.get("/static/index.html")
    assert response.status_code == 404


async def test_api_responses_carry_security_headers(client: AsyncClient) -> None:
    """JSON responses, including errors, get ``nosniff`` and ``no-referrer``."""
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"


async def test_index_is_not_in_openapi_schema(client: AsyncClient) -> None:
    """The page route is not documented as an API endpoint."""
    response = await client.get("/openapi.json")
    assert "/" not in response.json()["paths"]


async def test_unknown_path_still_returns_json_404(client: AsyncClient) -> None:
    """Serving the page does not swallow unknown paths."""
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
