"""Database queries for ``Task``.

Functions only flush; the calling service owns the transaction and commits.
"""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task


async def unassign_user_in_project(session: AsyncSession, project_id: int, user_id: int) -> None:
    """Clear ``assignee_id`` on every task of a project assigned to a user.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project_id : int
        Project identifier.
    user_id : int
        Assignee to remove.
    """
    await session.execute(
        update(Task)
        .where(Task.project_id == project_id, Task.assignee_id == user_id)
        .values(assignee_id=None),
    )
