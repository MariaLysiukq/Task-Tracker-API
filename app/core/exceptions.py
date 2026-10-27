"""Domain errors raised by services and mapped to HTTP responses in ``app.main``."""

from fastapi import status


class DomainError(Exception):
    """Base class for business-rule violations.

    Parameters
    ----------
    detail : str
        Client-safe error message.
    """

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class UnauthorizedError(DomainError):
    """Missing or invalid credentials."""

    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(DomainError):
    """Authenticated user lacks rights for the action."""

    status_code = status.HTTP_403_FORBIDDEN


class NotFoundError(DomainError):
    """Resource does not exist or is hidden from the user."""

    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    """Action conflicts with the current state."""

    status_code = status.HTTP_409_CONFLICT


class InvalidDataError(DomainError):
    """Input is well-formed but violates a business rule."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
