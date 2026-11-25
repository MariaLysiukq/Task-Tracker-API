"""Schemas for projects and project members."""

from datetime import datetime
from typing import Annotated, ClassVar

from pydantic import PositiveInt, StringConstraints

from app._detail.constants import DESCRIPTION_MAX_LENGTH, PROJECT_NAME_MAX_LENGTH
from app.models import MembershipRole
from app.schemas.common import PatchModel, ReadModel, RequestModel

ProjectName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=PROJECT_NAME_MAX_LENGTH),
]
Description = Annotated[str, StringConstraints(max_length=DESCRIPTION_MAX_LENGTH)]


class ProjectCreate(RequestModel):
    """Project creation request body."""

    name: ProjectName
    description: Description | None = None


class ProjectUpdate(PatchModel):
    """Partial project update; ``description`` may be cleared with ``null``."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset({"description"})
    name: ProjectName | None = None
    description: Description | None = None


class ProjectRead(ReadModel):
    """Project representation."""

    id: int
    name: str
    description: str | None
    owner_id: int
    created_at: datetime
    updated_at: datetime


class MemberCreate(RequestModel):
    """Request to add an already registered user to a project."""

    user_id: PositiveInt


class MemberRead(ReadModel):
    """Project membership representation."""

    project_id: int
    user_id: int
    role: MembershipRole
    created_at: datetime
