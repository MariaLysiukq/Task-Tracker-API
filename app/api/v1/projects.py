"""Project endpoints."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, PageDep, SessionDep
from app.schemas.common import Page
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services import project as project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    user: CurrentUserDep,
    session: SessionDep,
) -> ProjectRead:
    """Create a project owned by the current user.

    Parameters
    ----------
    data : ProjectCreate
        Name and optional description.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    ProjectRead
        The created project.
    """
    return ProjectRead.model_validate(await project_service.create_project(session, user, data))


@router.get("")
async def list_projects(
    page: PageDep, user: CurrentUserDep, session: SessionDep
) -> Page[ProjectRead]:
    """List the current user's projects, newest first.

    Parameters
    ----------
    page : PageParams
        ``limit`` (1-100) and ``offset`` query parameters.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    Page[ProjectRead]
        One page of projects with the total count.
    """
    items, total = await project_service.list_projects(session, user, page)
    return Page[ProjectRead](
        items=[ProjectRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{project_id}")
async def read_project(project_id: int, user: CurrentUserDep, session: SessionDep) -> ProjectRead:
    """Return a project of which the current user is a member.

    Parameters
    ----------
    project_id : int
        Project identifier.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    ProjectRead
        The project (404 for non-members).
    """
    project = await project_service.get_member_project(session, user, project_id)
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}")
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    user: CurrentUserDep,
    session: SessionDep,
) -> ProjectRead:
    """Update a project partially (owner only).

    Parameters
    ----------
    project_id : int
        Project identifier.
    data : ProjectUpdate
        Fields to change.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    ProjectRead
        The updated project (403 for members, 404 for non-members).
    """
    project = await project_service.update_project(session, user, project_id, data)
    return ProjectRead.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, user: CurrentUserDep, session: SessionDep) -> None:
    """Delete a project with its memberships, tasks and comments (owner only).

    Parameters
    ----------
    project_id : int
        Project identifier.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.
    """
    await project_service.delete_project(session, user, project_id)
