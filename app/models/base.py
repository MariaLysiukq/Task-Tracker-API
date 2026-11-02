"""Declarative base and shared column mixins for all ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app._detail.helpers import utc_now

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class holding the shared metadata used by Alembic."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    """Adds a timezone-aware UTC ``created_at`` column."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )


class TimestampMixin(CreatedAtMixin):
    """Adds timezone-aware UTC ``created_at`` and ``updated_at`` columns."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        onupdate=utc_now,
    )
