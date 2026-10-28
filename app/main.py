"""Application entry point."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.exceptions import DomainError


async def domain_error_handler(_: Request, error: DomainError) -> JSONResponse:
    """Convert a domain error into a JSON error response.

    Parameters
    ----------
    _ : Request
        Incoming request (unused).
    error : DomainError
        Raised business-rule violation.

    Returns
    -------
    JSONResponse
        Response with the error status code, ``{"detail": ...}`` body and error headers.
    """
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail},
        headers=error.headers,
    )


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Returns
    -------
    FastAPI
        Application with ``/api/v1`` routes and error handlers.
    """
    app = FastAPI(title="Task Tracker API", version="0.1.0")
    app.exception_handler(DomainError)(domain_error_handler)
    app.include_router(api_router)
    return app


app = create_app()
