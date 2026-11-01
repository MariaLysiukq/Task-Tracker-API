"""Route serving the single-page web client from ``frontend/index.html``."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

INDEX_FILE = Path(__file__).resolve().parents[2] / "frontend" / "index.html"

router = APIRouter(include_in_schema=False)


@router.get("/")
async def index() -> FileResponse:
    """Serve the web client page.

    Returns
    -------
    FileResponse
        The static HTML page; it talks to the API under ``/api/v1``.
    """
    return FileResponse(INDEX_FILE, media_type="text/html")
