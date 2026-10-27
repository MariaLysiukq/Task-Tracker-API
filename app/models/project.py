"""Project model."""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app._detail.constants import PROJECT_NAME_MAX_LENGTH
from app.models.base import Base, TimestampMixin


class Project(TimestampMixin, Base):
    """Team project owned by one user.

    ``owner_id`` uses ``RESTRICT``: an owner's account cannot be deleted while
    they own projects (the service reports this as 409).
    """

    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(PROJECT_NAME_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
