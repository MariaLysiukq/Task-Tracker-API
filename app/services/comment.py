"""Comment rules: members comment on tasks; only the author edits or deletes.

A comment is hidden (404) from users who are not members of its task's project;
a member who is not the author gets 403 on edit and delete.
"""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import Comment, User
from app.repositories import comment as comment_repo
from app.repositories import membership as membership_repo
from app.repositories import task as task_repo
from app.schemas.comment import CommentCreate, CommentUpdate
from app.schemas.common import PageParams
from app.services.task import get_member_task

COMMENT_NOT_FOUND = "Comment not found"
NOT_COMMENT_AUTHOR = "Only the author can change this comment"


async def get_authored_comment(session: AsyncSession, user: User, comment_id: int) -> Comment:
    """Return a comment written by the user, who is still a project member.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Authenticated user.
    comment_id : int
        Comment identifier.

    Returns
    -------
    Comment
        The comment.

    Raises
    ------
    NotFoundError
        If the comment does not exist or the user is not a member of its project.
    ForbiddenError
        If the user is a member but not the author.
    """
    comment = await comment_repo.get_by_id(session, comment_id)
    task = None if comment is None else await task_repo.get_by_id(session, comment.task_id)
    if (
        comment is None
        or task is None
        or await membership_repo.get(session, task.project_id, user.id) is None
    ):
        raise NotFoundError(COMMENT_NOT_FOUND)
    if comment.author_id != user.id:
        raise ForbiddenError(NOT_COMMENT_AUTHOR)
    return comment


async def create_comment(
    session: AsyncSession,
    user: User,
    task_id: int,
    data: CommentCreate,
) -> Comment:
    """Add a comment to a task of the user's project.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user, the author.
    task_id : int
        Task identifier.
    data : CommentCreate
        Validated comment text.

    Returns
    -------
    Comment
        The new comment.

    Raises
    ------
    NotFoundError
        If the task does not exist or the user is not a member of its project.
    """
    task = await get_member_task(session, user, task_id)
    comment = await comment_repo.create(session, task_id=task.id, author_id=user.id, body=data.body)
    await session.commit()
    return comment


async def list_comments(
    session: AsyncSession,
    user: User,
    task_id: int,
    page: PageParams,
) -> tuple[Sequence[Comment], int]:
    """Return one page of a task's comments, newest first.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Authenticated user.
    task_id : int
        Task identifier.
    page : PageParams
        ``limit`` and ``offset``.

    Returns
    -------
    tuple[Sequence[Comment], int]
        Page items and the total count.

    Raises
    ------
    NotFoundError
        If the task does not exist or the user is not a member of its project.
    """
    await get_member_task(session, user, task_id)
    return await comment_repo.list_for_task(
        session,
        task_id,
        limit=page.limit,
        offset=page.offset,
    )


async def update_comment(
    session: AsyncSession,
    user: User,
    comment_id: int,
    data: CommentUpdate,
) -> Comment:
    """Edit the text of the user's own comment.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    comment_id : int
        Comment identifier.
    data : CommentUpdate
        New comment text.

    Returns
    -------
    Comment
        The updated comment.

    Raises
    ------
    NotFoundError
        If the comment does not exist or the user is not a member of its project.
    ForbiddenError
        If the user is not the author.
    """
    comment = await get_authored_comment(session, user, comment_id)
    await comment_repo.update_body(session, comment, data.body)
    await session.commit()
    return comment


async def delete_comment(session: AsyncSession, user: User, comment_id: int) -> None:
    """Delete the user's own comment.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    comment_id : int
        Comment identifier.

    Raises
    ------
    NotFoundError
        If the comment does not exist or the user is not a member of its project.
    ForbiddenError
        If the user is not the author.
    """
    comment = await get_authored_comment(session, user, comment_id)
    await comment_repo.delete(session, comment)
    await session.commit()
