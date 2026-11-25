"""Project member rules: members list, owner adds and removes members.

The owner cannot be removed (409); removing a member unassigns their tasks
in the project in the same transaction.
"""

from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models import Membership, MembershipRole, User
from app.repositories import membership as membership_repo
from app.repositories import task as task_repo
from app.repositories import user as user_repo
from app.schemas.common import PageParams
from app.schemas.project import MemberCreate
from app.services.project import get_member_project, get_owned_project

USER_NOT_FOUND = "User not found"
MEMBER_NOT_FOUND = "Member not found"
ALREADY_MEMBER = "User is already a project member"
OWNER_NOT_REMOVABLE = "The project owner cannot be removed; delete the project instead"


async def list_members(
    session: AsyncSession,
    user: User,
    project_id: int,
    page: PageParams,
) -> tuple[Sequence[Membership], int]:
    """Return one page of a project's members, newest first.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Authenticated user.
    project_id : int
        Project identifier.
    page : PageParams
        ``limit`` and ``offset``.

    Returns
    -------
    tuple[Sequence[Membership], int]
        Page items and the total count.

    Raises
    ------
    NotFoundError
        If the project does not exist or the user is not a member.
    """
    await get_member_project(session, user, project_id)
    return await membership_repo.list_for_project(
        session,
        project_id,
        limit=page.limit,
        offset=page.offset,
    )


async def add_member(
    session: AsyncSession,
    user: User,
    project_id: int,
    data: MemberCreate,
) -> Membership:
    """Add a registered user to an owned project as ``member``.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    project_id : int
        Project identifier.
    data : MemberCreate
        Identifier of the user to add.

    Returns
    -------
    Membership
        The new membership.

    Raises
    ------
    NotFoundError
        If the project or the user does not exist, or the caller is not a member.
    ForbiddenError
        If the caller is not the owner.
    ConflictError
        If the user is already a member.
    """
    await get_owned_project(session, user, project_id)
    if await user_repo.get_by_id(session, data.user_id) is None:
        raise NotFoundError(USER_NOT_FOUND)
    if await membership_repo.get(session, project_id, data.user_id) is not None:
        raise ConflictError(ALREADY_MEMBER)
    try:
        membership = await membership_repo.create(
            session,
            project_id=project_id,
            user_id=data.user_id,
            role=MembershipRole.MEMBER,
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise ConflictError(ALREADY_MEMBER) from error
    return membership


async def remove_member(session: AsyncSession, user: User, project_id: int, user_id: int) -> None:
    """Remove a member from an owned project and unassign their tasks there.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    project_id : int
        Project identifier.
    user_id : int
        Identifier of the member to remove.

    Raises
    ------
    NotFoundError
        If the project does not exist, the caller is not a member,
        or ``user_id`` is not a member.
    ForbiddenError
        If the caller is not the owner.
    ConflictError
        If ``user_id`` is the project owner.
    """
    project = await get_owned_project(session, user, project_id)
    if user_id == project.owner_id:
        raise ConflictError(OWNER_NOT_REMOVABLE)
    membership = await membership_repo.get(session, project_id, user_id)
    if membership is None:
        raise NotFoundError(MEMBER_NOT_FOUND)
    await task_repo.unassign_user_in_project(session, project_id, user_id)
    await membership_repo.delete(session, membership)
    await session.commit()
