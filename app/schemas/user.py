"""Schemas for registration, login and the own profile."""

from datetime import datetime
from typing import Annotated, ClassVar, Literal, Self

from pydantic import AfterValidator, EmailStr, Field, SecretStr, StringConstraints, model_validator

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
# Checked against the stored hash, so only the upper bound is enforced (like login).
ExistingPassword = Annotated[SecretStr, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]
CURRENT_PASSWORD_REQUIRED = "current_password is required to change email or password"  # noqa: S105 - message
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
    password: ExistingPassword


class UserUpdate(PatchModel):
    """Partial update of the own profile; no field may be ``null``.

    Changing ``email`` or ``password`` also requires ``current_password``, so a
    stolen access token alone cannot take over the account.
    """

    sensitive_fields: ClassVar[frozenset[str]] = frozenset({"email", "password"})
    email: NormalizedEmail | None = None
    password: NewPassword | None = None
    full_name: FullName | None = None
    current_password: ExistingPassword | None = None

    @model_validator(mode="after")
    def require_current_password(self) -> Self:
        """Demand ``current_password`` when a sensitive field is sent.

        Returns
        -------
        Self
            The validated model.

        Raises
        ------
        ValueError
            If ``email`` or ``password`` is sent without ``current_password``.
        """
        if self.model_fields_set & self.sensitive_fields and self.current_password is None:
            raise ValueError(CURRENT_PASSWORD_REQUIRED)
        return self

    def changes(self) -> dict[str, object]:
        """Return the profile fields to write; ``current_password`` is never included.

        Returns
        -------
        dict[str, object]
            Explicitly sent profile fields and their values.
        """
        return self.model_dump(exclude_unset=True, exclude={"current_password"})


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
