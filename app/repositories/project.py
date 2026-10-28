"""Database queries for ``Project``."""

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project


async def exists_owned_by(session: AsyncSession, user_id: int) -> bool:
    """Check whether a user owns at least one project.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user_id : int
        User identifier.

    Returns
    -------
    bool
        ``True`` if any project has ``owner_id == user_id``.
    """
    return bool(await session.scalar(select(exists().where(Project.owner_id == user_id))))
