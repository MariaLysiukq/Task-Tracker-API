"""Web client: the page at ``/`` with its security headers and assets under ``/static``."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"
STATIC_DIR = FRONTEND_DIR / "static"
# Only same-origin scripts, styles, fonts and API calls; the page cannot be framed.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)
# Revalidate on every load (304 via ETag when unchanged), so browsers never run an old client.
CACHE_CONTROL = "no-cache"
PAGE_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Frame-Options": "DENY",
    "Cache-Control": CACHE_CONTROL,
}

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


class RevalidatedStaticFiles(StaticFiles):
    """Static files that browsers must revalidate before reuse."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        """Serve a static file with ``Cache-Control: no-cache``.

        Without it browsers cache assets heuristically and can pair a new page
        with an old stylesheet or script.

        Parameters
        ----------
        path : str
            File path relative to the static directory.
        scope : Scope
            ASGI request scope.

        Returns
        -------
        Response
            The file, a 304 Not Modified, or a 404, with the cache header set.
        """
        response = await super().get_response(path, scope)
        response.headers.setdefault("Cache-Control", CACHE_CONTROL)
        return response
