"""Database queries for ``Project``.

Functions only flush; the calling service owns the transaction and commits.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Membership, Project


async def create(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    owner_id: int,
) -> Project:
    """Insert a new project.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    name : str
        Project name.
    description : str | None
        Optional description.
    owner_id : int
        Identifier of the owning user.

    Returns
    -------
    Project
        The flushed project with ``id`` and timestamps set.
    """
    project = Project(name=name, description=description, owner_id=owner_id)
    session.add(project)
    await session.flush()
    return project


async def get_by_id(session: AsyncSession, project_id: int) -> Project | None:
    """Return a project by primary key.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project_id : int
        Project identifier.

    Returns
    -------
    Project | None
        The project, or ``None`` if it does not exist.
    """
    return await session.get(Project, project_id)


async def list_for_member(
    session: AsyncSession,
    user_id: int,
    *,
    limit: int,
    offset: int,
) -> tuple[Sequence[Project], int]:
    """Return one page of the projects a user is a member of, newest first.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user_id : int
        Member identifier.
    limit : int
        Maximum number of items.
    offset : int
        Number of items to skip.

    Returns
    -------
    tuple[Sequence[Project], int]
        Page items ordered by ``created_at DESC, id DESC`` and the total count.
    """
    member_of = Membership.user_id == user_id
    total = await session.scalar(
        select(func.count()).select_from(Membership).where(member_of),
    )
    items = await session.scalars(
        select(Project)
        .join(Membership, Membership.project_id == Project.id)
        .where(member_of)
        .order_by(Project.created_at.desc(), Project.id.desc())
        .limit(limit)
        .offset(offset),
    )
    return items.all(), total or 0


async def update(session: AsyncSession, project: Project, values: Mapping[str, Any]) -> Project:
    """Apply field changes to a project.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project : Project
        Persistent project to change.
    values : Mapping[str, Any]
        Column names mapped to new values (``name``, ``description``).

    Returns
    -------
    Project
        The flushed project with ``updated_at`` refreshed.
    """
    for field, value in values.items():
        setattr(project, field, value)
    await session.flush()
    return project


async def delete(session: AsyncSession, project: Project) -> None:
    """Delete a project; memberships, tasks and comments cascade in the database.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project : Project
        Persistent project to delete.
    """
    await session.delete(project)
    await session.flush()


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
