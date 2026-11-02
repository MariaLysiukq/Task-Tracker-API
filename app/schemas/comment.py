"""Schemas for task comments."""

from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from app._detail.constants import COMMENT_BODY_MAX_LENGTH
from app.schemas.common import ReadModel, RequestModel

CommentBody = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=COMMENT_BODY_MAX_LENGTH),
]


class CommentCreate(RequestModel):
    """Comment creation request body."""

    body: CommentBody


class CommentUpdate(RequestModel):
    """Comment edit request body; ``body`` is the only editable field."""

    body: CommentBody


class CommentRead(ReadModel):
    """Comment representation."""

    id: int
    task_id: int
    author_id: int
    body: str
    created_at: datetime
    updated_at: datetime
