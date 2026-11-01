"""Web client: the page at ``/`` with its security headers and assets under ``/static``."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"
STATIC_DIR = FRONTEND_DIR / "static"
# Only same-origin scripts, styles, fonts and API calls; the page cannot be framed.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)
PAGE_HEADERS = {"Content-Security-Policy": CONTENT_SECURITY_POLICY, "X-Frame-Options": "DENY"}

router = APIRouter(include_in_schema=False)


@router.get("/")
async def index() -> FileResponse:
    """Serve the web client page.

    Returns
    -------
    FileResponse
        The static HTML page with a strict Content-Security-Policy; it loads
        ``/static`` assets and talks to the API under ``/api/v1``.
    """
    return FileResponse(INDEX_FILE, media_type="text/html", headers=PAGE_HEADERS)
