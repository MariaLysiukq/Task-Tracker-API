"""Tests for ``app.services.comment``."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import Comment, Project, Task, User
from app.schemas.comment import CommentCreate, CommentUpdate
from app.schemas.common import PageParams
from app.schemas.task import TaskCreate
from app.services import comment as comment_service
from app.services import membership as membership_service
from app.services import task as task_service
from tests.unit.service_helpers import make_team


async def make_comment(session: AsyncSession) -> tuple[Comment, Task, Project, User, User, User]:
    """Create a team, a task and a comment written by the member.

    Parameters
    ----------
    session : AsyncSession
        Test session.

    Returns
    -------
    tuple[Comment, Task, Project, User, User, User]
        Comment, task, project, owner, member (author) and outsider.
    """
    project, owner, member, outsider = await make_team(session)
    task = await task_service.create_task(session, owner, project.id, TaskCreate(title="X"))
    comment = await comment_service.create_comment(
        session, member, task.id, CommentCreate(body="Hi")
    )
    return comment, task, project, owner, member, outsider


async def test_create_comment_by_member(db_session: AsyncSession) -> None:
    """A member comments on a task and becomes the author."""
    comment, task, _, _, member, _ = await make_comment(db_session)
    assert (comment.task_id, comment.author_id, comment.body) == (task.id, member.id, "Hi")


async def test_create_and_list_hidden_from_outsider(db_session: AsyncSession) -> None:
    """A non-member or a missing task gives 404 for create and list."""
    _, task, _, _, _, outsider = await make_comment(db_session)
    for task_id in (task.id, task.id + 1):
        with pytest.raises(NotFoundError, match=task_service.TASK_NOT_FOUND):
            await comment_service.create_comment(
                db_session, outsider, task_id, CommentCreate(body="X")
            )
        with pytest.raises(NotFoundError, match=task_service.TASK_NOT_FOUND):
            await comment_service.list_comments(db_session, outsider, task_id, PageParams())


async def test_list_comments_newest_first(db_session: AsyncSession) -> None:
    """Members see every comment of the task, newest first."""
    comment, task, _, owner, _, _ = await make_comment(db_session)
    newer = await comment_service.create_comment(
        db_session, owner, task.id, CommentCreate(body="Reply")
    )
    items, total = await comment_service.list_comments(db_session, owner, task.id, PageParams())
    assert (list(items), total) == ([newer, comment], 2)


async def test_update_and_delete_by_author(db_session: AsyncSession) -> None:
    """The author edits and deletes their comment."""
    comment, _, _, _, member, _ = await make_comment(db_session)
    updated = await comment_service.update_comment(
        db_session, member, comment.id, CommentUpdate(body="Edited")
    )
    assert updated.body == "Edited"
    await comment_service.delete_comment(db_session, member, comment.id)
    assert (await db_session.scalars(select(Comment))).all() == []


async def test_update_and_delete_by_other_member_forbidden(db_session: AsyncSession) -> None:
    """Another member, even the owner, gets 403 and the comment is kept."""
    comment, _, _, owner, _, _ = await make_comment(db_session)
    with pytest.raises(ForbiddenError, match=comment_service.NOT_COMMENT_AUTHOR):
        await comment_service.update_comment(db_session, owner, comment.id, CommentUpdate(body="X"))
    with pytest.raises(ForbiddenError, match=comment_service.NOT_COMMENT_AUTHOR):
        await comment_service.delete_comment(db_session, owner, comment.id)
    await db_session.refresh(comment)
    assert comment.body == "Hi"


async def test_update_and_delete_hidden_from_outsider(db_session: AsyncSession) -> None:
    """A non-member or a missing comment gives 404."""
    comment, _, _, _, member, outsider = await make_comment(db_session)
    for user, comment_id in ((outsider, comment.id), (member, comment.id + 1)):
        with pytest.raises(NotFoundError, match=comment_service.COMMENT_NOT_FOUND):
            await comment_service.update_comment(
                db_session, user, comment_id, CommentUpdate(body="X")
            )
        with pytest.raises(NotFoundError, match=comment_service.COMMENT_NOT_FOUND):
            await comment_service.delete_comment(db_session, user, comment_id)


async def test_removed_author_loses_comment_access(db_session: AsyncSession) -> None:
    """After removal from the project the author gets 404 on their own comment."""
    comment, task, project, owner, member, _ = await make_comment(db_session)
    await membership_service.remove_member(db_session, owner, project.id, member.id)
    with pytest.raises(NotFoundError, match=comment_service.COMMENT_NOT_FOUND):
        await comment_service.update_comment(
            db_session, member, comment.id, CommentUpdate(body="X")
        )
    with pytest.raises(NotFoundError, match=task_service.TASK_NOT_FOUND):
        await comment_service.list_comments(db_session, member, task.id, PageParams())
