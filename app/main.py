"""Application entry point."""

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
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
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(errors)},
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
    app.exception_handler(RequestValidationError)(validation_error_handler)
    app.include_router(api_router)
    return app


app = create_app()
