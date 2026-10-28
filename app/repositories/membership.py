"""Database queries for ``Membership``.

Functions only flush; the calling service owns the transaction and commits.
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Membership, MembershipRole


async def create(
    session: AsyncSession,
    *,
    project_id: int,
    user_id: int,
    role: MembershipRole,
) -> Membership:
    """Insert a membership.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project_id : int
        Project identifier.
    user_id : int
        Member identifier.
    role : MembershipRole
        Role inside the project.

    Returns
    -------
    Membership
        The flushed membership.

    Raises
    ------
    sqlalchemy.exc.IntegrityError
        If the user is already a member or the project/user does not exist.
    """
    membership = Membership(project_id=project_id, user_id=user_id, role=role)
    session.add(membership)
    await session.flush()
    return membership


async def get(session: AsyncSession, project_id: int, user_id: int) -> Membership | None:
    """Return the membership of a user in a project.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project_id : int
        Project identifier.
    user_id : int
        User identifier.

    Returns
    -------
    Membership | None
        The membership, or ``None`` if the user is not a member.
    """
    result = await session.scalars(
        select(Membership).where(
            Membership.project_id == project_id,
            Membership.user_id == user_id,
        ),
    )
    return result.one_or_none()


async def list_for_project(
    session: AsyncSession,
    project_id: int,
    *,
    limit: int,
    offset: int,
) -> tuple[Sequence[Membership], int]:
    """Return one page of a project's members, newest first.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    project_id : int
        Project identifier.
    limit : int
        Maximum number of items.
    offset : int
        Number of items to skip.

    Returns
    -------
    tuple[Sequence[Membership], int]
        Page items ordered by ``created_at DESC, id DESC`` and the total count.
    """
    in_project = Membership.project_id == project_id
    total = await session.scalar(
        select(func.count()).select_from(Membership).where(in_project),
    )
    items = await session.scalars(
        select(Membership)
        .where(in_project)
        .order_by(Membership.created_at.desc(), Membership.id.desc())
        .limit(limit)
        .offset(offset),
    )
    return items.all(), total or 0
