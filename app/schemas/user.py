"""Schemas for registration, login and the own profile."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, EmailStr, Field, SecretStr, StringConstraints

from app._detail.constants import (
    EMAIL_MAX_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USER_FULL_NAME_MAX_LENGTH,
)
from app.schemas.common import PatchModel, ReadModel, RequestModel

NormalizedEmail = Annotated[
    EmailStr,
    Field(max_length=EMAIL_MAX_LENGTH),
    AfterValidator(str.lower),
]
NewPassword = Annotated[
    SecretStr,
    Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
]
FullName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=USER_FULL_NAME_MAX_LENGTH),
]


class UserCreate(RequestModel):
    """Registration request body."""

    email: NormalizedEmail
    password: NewPassword
    full_name: FullName


class LoginRequest(RequestModel):
    """Login request body; the password policy is not revealed here."""

    email: NormalizedEmail
    password: Annotated[SecretStr, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]


class UserUpdate(PatchModel):
    """Partial update of the own profile; no field may be ``null``."""

    email: NormalizedEmail | None = None
    password: NewPassword | None = None
    full_name: FullName | None = None


class UserRead(ReadModel):
    """Public user representation; never contains the password hash."""

    id: int
    email: str
    full_name: str
    created_at: datetime
    updated_at: datetime


class TokenRead(ReadModel):
    """JWT access token issued on login."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth2 scheme name, not a secret
