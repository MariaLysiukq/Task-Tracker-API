"""User account model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app._detail.constants import (
    EMAIL_MAX_LENGTH,
    PASSWORD_HASH_MAX_LENGTH,
    USER_FULL_NAME_MAX_LENGTH,
)
from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """Registered user.

    ``email`` is stored lowercase (normalized by the service layer).
    """

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(PASSWORD_HASH_MAX_LENGTH))
    full_name: Mapped[str] = mapped_column(String(USER_FULL_NAME_MAX_LENGTH))
