"""Project rules: owner membership on create, member-only access, owner-only changes.

A project is hidden (404) from non-members; members lacking rights get 403.
"""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import MembershipRole, Project, User
from app.repositories import membership as membership_repo
from app.repositories import project as project_repo
from app.schemas.common import PageParams
from app.schemas.project import ProjectCreate, ProjectUpdate

PROJECT_NOT_FOUND = "Project not found"
OWNER_ONLY = "Only the project owner can do this"


async def get_member_project(session: AsyncSession, user: User, project_id: int) -> Project:
    """Return a project the user is a member of.

    Shared access check for projects and their nested resources.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Authenticated user.
    project_id : int
        Project identifier.

    Returns
    -------
    Project
        The project.

    Raises
    ------
    NotFoundError
        If the project does not exist or the user is not a member.
    """
    project = await project_repo.get_by_id(session, project_id)
    if project is None or await membership_repo.get(session, project_id, user.id) is None:
        raise NotFoundError(PROJECT_NOT_FOUND)
    return project


async def get_owned_project(session: AsyncSession, user: User, project_id: int) -> Project:
    """Return a project the user owns.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Authenticated user.
    project_id : int
        Project identifier.

    Returns
    -------
    Project
        The project.

    Raises
    ------
    NotFoundError
        If the project does not exist or the user is not a member.
    ForbiddenError
        If the user is a member but not the owner.
    """
    project = await get_member_project(session, user, project_id)
    if project.owner_id != user.id:
        raise ForbiddenError(OWNER_ONLY)
    return project


async def create_project(session: AsyncSession, user: User, data: ProjectCreate) -> Project:
    """Create a project with the creator as owner, in one transaction.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated creator.
    data : ProjectCreate
        Validated project data.

    Returns
    -------
    Project
        The new project.
    """
    project = await project_repo.create(
        session,
        name=data.name,
        description=data.description,
        owner_id=user.id,
    )
    await membership_repo.create(
        session,
        project_id=project.id,
        user_id=user.id,
        role=MembershipRole.OWNER,
    )
    await session.commit()
    return project


async def list_projects(
    session: AsyncSession,
    user: User,
    page: PageParams,
) -> tuple[Sequence[Project], int]:
    """Return one page of the user's projects, newest first.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    user : User
        Authenticated user.
    page : PageParams
        ``limit`` and ``offset``.

    Returns
    -------
    tuple[Sequence[Project], int]
        Page items and the total count.
    """
    return await project_repo.list_for_member(
        session,
        user.id,
        limit=page.limit,
        offset=page.offset,
    )


async def update_project(
    session: AsyncSession,
    user: User,
    project_id: int,
    data: ProjectUpdate,
) -> Project:
    """Apply a partial update to an owned project.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    project_id : int
        Project identifier.
    data : ProjectUpdate
        Fields sent by the client.

    Returns
    -------
    Project
        The updated project.

    Raises
    ------
    NotFoundError
        If the project does not exist or the user is not a member.
    ForbiddenError
        If the user is not the owner.
    """
    project = await get_owned_project(session, user, project_id)
    await project_repo.update(session, project, data.changes())
    await session.commit()
    return project


async def delete_project(session: AsyncSession, user: User, project_id: int) -> None:
    """Delete an owned project; memberships, tasks and comments cascade.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    project_id : int
        Project identifier.

    Raises
    ------
    NotFoundError
        If the project does not exist or the user is not a member.
    ForbiddenError
        If the user is not the owner.
    """
    project = await get_owned_project(session, user, project_id)
    await project_repo.delete(session, project)
    await session.commit()
