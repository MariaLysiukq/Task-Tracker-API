"""Comment endpoints: creation and listing on a task, editing by comment id."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, PageDep, SessionDep
from app.schemas.comment import CommentCreate, CommentRead, CommentUpdate
from app.schemas.common import Page
from app.services import comment as comment_service

router = APIRouter(tags=["comments"])


@router.post("/tasks/{task_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    task_id: int,
    data: CommentCreate,
    user: CurrentUserDep,
    session: SessionDep,
) -> CommentRead:
    """Comment on a task (any member of its project).

    Parameters
    ----------
    task_id : int
        Task identifier.
    data : CommentCreate
        Comment text.
    user : User
        Authenticated user, the author.
    session : AsyncSession
        Request database session.

    Returns
    -------
    CommentRead
        The created comment (404 for non-members).
    """
    comment = await comment_service.create_comment(session, user, task_id, data)
    return CommentRead.model_validate(comment)


@router.get("/tasks/{task_id}/comments")
async def list_comments(
    task_id: int,
    page: PageDep,
    user: CurrentUserDep,
    session: SessionDep,
) -> Page[CommentRead]:
    """List a task's comments, newest first (any member).

    Parameters
    ----------
    task_id : int
        Task identifier.
    page : PageParams
        ``limit`` (1-100) and ``offset`` query parameters.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    Page[CommentRead]
        One page of comments with the total count (404 for non-members).
    """
    items, total = await comment_service.list_comments(session, user, task_id, page)
    return Page[CommentRead](
        items=[CommentRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.patch("/comments/{comment_id}")
async def update_comment(
    comment_id: int,
    data: CommentUpdate,
    user: CurrentUserDep,
    session: SessionDep,
) -> CommentRead:
    """Edit a comment (author who is still a member).

    Parameters
    ----------
    comment_id : int
        Comment identifier.
    data : CommentUpdate
        New comment text.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    CommentRead
        The updated comment (403 for other members, 404 for non-members).
    """
    comment = await comment_service.update_comment(session, user, comment_id, data)
    return CommentRead.model_validate(comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(comment_id: int, user: CurrentUserDep, session: SessionDep) -> None:
    """Delete a comment (author who is still a member).

    Parameters
    ----------
    comment_id : int
        Comment identifier.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.
    """
    await comment_service.delete_comment(session, user, comment_id)
