"""Own-profile endpoints."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.user import UserRead, UserUpdate
from app.services import user as user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def read_me(user: CurrentUserDep) -> UserRead:
    """Return the authenticated user's profile.

    Parameters
    ----------
    user : User
        Authenticated user.

    Returns
    -------
    UserRead
        Own profile.
    """
    return UserRead.model_validate(user)


@router.patch("/me")
async def update_me(data: UserUpdate, user: CurrentUserDep, session: SessionDep) -> UserRead:
    """Update the own profile partially.

    Parameters
    ----------
    data : UserUpdate
        Fields to change.
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.

    Returns
    -------
    UserRead
        Updated profile (409 if the new email is taken).
    """
    return UserRead.model_validate(await user_service.update_profile(session, user, data))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUserDep, session: SessionDep) -> None:
    """Delete the own account (409 while owning projects).

    Parameters
    ----------
    user : User
        Authenticated user.
    session : AsyncSession
        Request database session.
    """
    await user_service.delete_account(session, user)
