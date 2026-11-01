"""Application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
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


async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    """Return 422 validation errors without echoing the submitted values.

    FastAPI's default handler includes each rejected ``input``, which can be a password.

    Parameters
    ----------
    _ : Request
        Incoming request (unused).
    error : RequestValidationError
        Request body, query or path validation failure.

    Returns
    -------
    JSONResponse
        422 response with ``{"detail": [...]}`` errors stripped of ``input``.
    """
    errors = [
        {key: value for key, value in item.items() if key != "input"} for item in error.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(errors)},
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate settings at server start-up instead of on the first request.

    Parameters
    ----------
    _ : FastAPI
        Application being started (unused).

    Yields
    ------
    None
        Control while the application serves requests.

    Raises
    ------
    pydantic.ValidationError
        If a required setting is missing or invalid (e.g. ``JWT_SECRET`` too short).
    """
    get_settings()
    yield


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Returns
    -------
    FastAPI
        Application with ``/api/v1`` routes, error handlers and start-up settings check.
    """
    app = FastAPI(title="Task Tracker API", version="0.1.0", lifespan=lifespan)
    app.exception_handler(DomainError)(domain_error_handler)
    app.exception_handler(RequestValidationError)(validation_error_handler)
    app.include_router(api_router)
    return app


app = create_app()
