"""Own-profile rules: update and account deletion."""

from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError
from app.core.security import hash_password, verify_password
from app.models import User
from app.repositories import project as project_repo
from app.repositories import user as user_repo
from app.schemas.user import UserUpdate
from app.services.auth import EMAIL_TAKEN

OWNS_PROJECTS = "Delete your projects before deleting the account"
WRONG_CURRENT_PASSWORD = "Current password is incorrect"  # noqa: S105 - message


async def update_profile(session: AsyncSession, user: User, data: UserUpdate) -> User:
    """Apply a partial profile update.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.
    data : UserUpdate
        Fields sent by the client; a new password is stored only as a hash.
        ``current_password`` (required by the schema for email/password changes)
        is verified before anything else, so a wrong one reveals nothing about
        other users' emails.

    Returns
    -------
    User
        The updated user.

    Raises
    ------
    ForbiddenError
        If ``current_password`` is sent and does not match.
    ConflictError
        If the new email belongs to another user.
    """
    current = data.current_password
    if current is not None and not verify_password(
        current.get_secret_value(), user.hashed_password
    ):
        raise ForbiddenError(WRONG_CURRENT_PASSWORD)
    changes = data.changes()
    password = changes.pop("password", None)
    if isinstance(password, SecretStr):
        changes["hashed_password"] = hash_password(password.get_secret_value())
    email = changes.get("email")
    if isinstance(email, str):
        owner = await user_repo.get_by_email(session, email)
        if owner is not None and owner.id != user.id:
            raise ConflictError(EMAIL_TAKEN)
    try:
        await user_repo.update(session, user, changes)
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise ConflictError(EMAIL_TAKEN) from error
    return user


async def delete_account(session: AsyncSession, user: User) -> None:
    """Delete the authenticated user's account.

    Memberships are removed and assigned tasks become unassigned by the database.

    Parameters
    ----------
    session : AsyncSession
        Active database session; committed on success.
    user : User
        Authenticated user.

    Raises
    ------
    ConflictError
        If the user still owns projects.
    """
    if await project_repo.exists_owned_by(session, user.id):
        raise ConflictError(OWNS_PROJECTS)
    await user_repo.delete(session, user)
    await session.commit()
