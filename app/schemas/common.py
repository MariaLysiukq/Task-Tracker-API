"""Shared schema building blocks: base models, UTC datetimes and pagination."""

from enum import StrEnum
from typing import Annotated, ClassVar, Self

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app._detail.constants import PAGE_LIMIT_DEFAULT, PAGE_LIMIT_MAX
from app._detail.helpers import to_utc

UTCDateTime = Annotated[AwareDatetime, AfterValidator(to_utc)]


class RequestModel(BaseModel):
    """Base for request bodies; unknown fields are rejected with 422."""

    model_config = ConfigDict(extra="forbid")


class PatchModel(RequestModel):
    """Base for partial updates.

    Omitted fields stay unchanged. An explicit ``null`` is accepted only for
    fields listed in ``nullable_fields``.
    """

    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> Self:
        """Reject ``null`` sent for a non-nullable field.

        Returns
        -------
        Self
            The validated model.

        Raises
        ------
        ValueError
            If a non-nullable field was explicitly set to ``null``.
        """
        invalid = sorted(
            name
            for name in self.model_fields_set - self.nullable_fields
            if getattr(self, name) is None
        )
        if invalid:
            raise ValueError(f"fields cannot be null: {', '.join(invalid)}")
        return self

    def changes(self) -> dict[str, object]:
        """Return only the fields sent by the client.

        Returns
        -------
        dict[str, object]
            Field names mapped to new values.
        """
        return self.model_dump(exclude_unset=True)


class ReadModel(BaseModel):
    """Base for responses built from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class SortOrder(StrEnum):
    """Sort direction."""

    ASC = "asc"
    DESC = "desc"


class PageParams(BaseModel):
    """Pagination query parameters.

    Attributes
    ----------
    limit : int
        Page size, 1 to ``PAGE_LIMIT_MAX``.
    offset : int
        Number of items to skip.
    """

    limit: int = Field(default=PAGE_LIMIT_DEFAULT, ge=1, le=PAGE_LIMIT_MAX)
    offset: int = Field(default=0, ge=0)


class Page[ItemT](BaseModel):
    """One page of a list response.

    Attributes
    ----------
    items : list[ItemT]
        Items of the current page.
    total : int
        Number of items matching the query.
    limit : int
        Requested page size.
    offset : int
        Requested offset.
    """

    items: list[ItemT]
    total: int
    limit: int
    offset: int
