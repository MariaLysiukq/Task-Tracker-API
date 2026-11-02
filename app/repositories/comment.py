"""Database queries for ``Comment``.

Functions only flush; the calling service owns the transaction and commits.
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment


async def create(session: AsyncSession, *, task_id: int, author_id: int, body: str) -> Comment:
    """Insert a new comment.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    task_id : int
        Commented task.
    author_id : int
        Comment author.
    body : str
        Comment text.

    Returns
    -------
    Comment
        The flushed comment with ``id`` and timestamps set.
    """
    comment = Comment(task_id=task_id, author_id=author_id, body=body)
    session.add(comment)
    await session.flush()
    return comment


async def get_by_id(session: AsyncSession, comment_id: int) -> Comment | None:
    """Return a comment by primary key.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    comment_id : int
        Comment identifier.

    Returns
    -------
    Comment | None
        The comment, or ``None`` if it does not exist.
    """
    return await session.get(Comment, comment_id)


async def list_for_task(
    session: AsyncSession,
    task_id: int,
    *,
    limit: int,
    offset: int,
) -> tuple[Sequence[Comment], int]:
    """Return one page of a task's comments, newest first.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    task_id : int
        Task identifier.
    limit : int
        Maximum number of items.
    offset : int
        Number of items to skip.

    Returns
    -------
    tuple[Sequence[Comment], int]
        Page items ordered by ``created_at DESC, id DESC`` and the total count.
    """
    of_task = Comment.task_id == task_id
    total = await session.scalar(select(func.count()).select_from(Comment).where(of_task))
    items = await session.scalars(
        select(Comment)
        .where(of_task)
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .limit(limit)
        .offset(offset),
    )
    return items.all(), total or 0


async def update_body(session: AsyncSession, comment: Comment, body: str) -> Comment:
    """Replace the text of a comment.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    comment : Comment
        Persistent comment to change.
    body : str
        New text.

    Returns
    -------
    Comment
        The flushed comment with ``updated_at`` refreshed.
    """
    comment.body = body
    await session.flush()
    return comment


async def delete(session: AsyncSession, comment: Comment) -> None:
    """Delete a comment.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    comment : Comment
        Persistent comment to delete.
    """
    await session.delete(comment)
    await session.flush()
