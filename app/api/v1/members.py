"""Project member endpoints."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, PageDep, SessionDep
from app.schemas.common import Page
from app.schemas.project import MemberCreate, MemberRead
from app.services import membership as membership_service

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])


@router.get("")
async def list_members(
    project_id: int,
    page: PageDep,
    user: CurrentUserDep,
    session: SessionDep,
) -> Page[MemberRead]:
    """List the members of a project, newest first.

    Parameters
    ----------
    project_id : int
        Project identifier.
    page : PageParams
        ``limit`` (1-100) and ``offset`` query parameters.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    Page[MemberRead]
        One page of members with the total count (404 for non-members).
    """
    items, total = await membership_service.list_members(session, user, project_id, page)
    return Page[MemberRead](
        items=[MemberRead.model_validate(item) for item in items],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: int,
    data: MemberCreate,
    user: CurrentUserDep,
    session: SessionDep,
) -> MemberRead:
    """Add a registered user to the project (owner only).

    Parameters
    ----------
    project_id : int
        Project identifier.
    data : MemberCreate
        Identifier of the user to add.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    MemberRead
        The new membership (403 for members, 404 for non-members or unknown user,
        409 if already a member).
    """
    membership = await membership_service.add_member(session, user, project_id, data)
    return MemberRead.model_validate(membership)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    project_id: int,
    user_id: int,
    user: CurrentUserDep,
    session: SessionDep,
) -> None:
    """Remove a member and unassign their tasks in the project (owner only).

    Parameters
    ----------
    project_id : int
        Project identifier.
    user_id : int
        Identifier of the member to remove.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.
    """
    await membership_service.remove_member(session, user, project_id, user_id)
