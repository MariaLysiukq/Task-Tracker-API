"""Shared factories for service unit tests."""

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MembershipRole, Project, User
from app.repositories import membership as membership_repo
from app.schemas.project import ProjectCreate
from app.schemas.user import UserCreate
from app.services import auth
from app.services import project as project_service


async def make_user(session: AsyncSession, email: str) -> User:
    """Register a user through the auth service.

    Parameters
    ----------
    session : AsyncSession
        Test session.
    email : str
        Email to register.

    Returns
    -------
    User
        Registered user.
    """
    data = UserCreate(email=email, password=SecretStr("password123"), full_name="Ann")
    return await auth.register(session, data)


async def make_team(session: AsyncSession) -> tuple[Project, User, User, User]:
    """Create a project with an owner, a member and an unrelated outsider.

    Parameters
    ----------
    session : AsyncSession
        Test session.

    Returns
    -------
    tuple[Project, User, User, User]
        Project, owner, member and outsider.
    """
    owner = await make_user(session, "owner@example.com")
    member = await make_user(session, "member@example.com")
    outsider = await make_user(session, "outsider@example.com")
    project = await project_service.create_project(session, owner, ProjectCreate(name="Alpha"))
    await membership_repo.create(
        session, project_id=project.id, user_id=member.id, role=MembershipRole.MEMBER
    )
    await session.commit()
    return project, owner, member, outsider
