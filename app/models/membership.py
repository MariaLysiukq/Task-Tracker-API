"""Project membership model."""

from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin


class MembershipRole(StrEnum):
    """Role of a user inside a project."""

    OWNER = "owner"
    MEMBER = "member"


class Membership(CreatedAtMixin, Base):
    """Link between a user and a project; the pair is unique."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[MembershipRole] = mapped_column(
        Enum(
            MembershipRole,
            name="membership_role",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda roles: [role.value for role in roles],
        ),
    )
