"""Task comment model."""

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app._detail.constants import COMMENT_BODY_MAX_LENGTH
from app.models.base import Base, TimestampMixin


class Comment(TimestampMixin, Base):
    """Comment on a task; removed together with its task or author."""

    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_task_id_created_at_id", "task_id", "created_at", "id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    body: Mapped[str] = mapped_column(String(COMMENT_BODY_MAX_LENGTH))
