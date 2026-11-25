"""Unit tests for ``app.services.project``."""

from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError, ForbiddenError, NotFoundError
from app.models import MembershipRole, User
from app.repositories import membership as membership_repo
from app.repositories import project as project_repo
from app.schemas.common import PageParams
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services import project as project_service
from tests.unit.service_helpers import make_team, make_user

ProjectAction = Callable[[AsyncSession, User, int], Awaitable[object]]


async def test_create_makes_creator_owner(db_session: AsyncSession) -> None:
    """The creator owns the project and gets an ``owner`` membership."""
    owner = await make_user(db_session, "owner@example.com")
    data = ProjectCreate(name="Alpha", description="Docs")
    project = await project_service.create_project(db_session, owner, data)
    assert project.owner_id == owner.id
    assert project.description == "Docs"
    membership = await membership_repo.get(db_session, project.id, owner.id)
    assert membership is not None
    assert membership.role == MembershipRole.OWNER


async def test_list_returns_projects_of_membership_only(db_session: AsyncSession) -> None:
    """Owners and members see the project; outsiders get an empty page."""
    project, owner, member, outsider = await make_team(db_session)
    for user in (owner, member):
        items, total = await project_service.list_projects(db_session, user, PageParams())
        assert [item.id for item in items] == [project.id]
        assert total == 1
    assert await project_service.list_projects(db_session, outsider, PageParams()) == ([], 0)


async def test_list_applies_page_params(db_session: AsyncSession) -> None:
    """``limit``/``offset`` are passed through; the total is unaffected."""
    owner = await make_user(db_session, "owner@example.com")
    for name in ("A", "B", "C"):
        await project_service.create_project(db_session, owner, ProjectCreate(name=name))
    items, total = await project_service.list_projects(
        db_session, owner, PageParams(limit=2, offset=2)
    )
    assert [item.name for item in items] == ["A"]
    assert total == 3


async def test_get_member_project_for_owner_and_member(db_session: AsyncSession) -> None:
    """Every member can read the project."""
    project, owner, member, _ = await make_team(db_session)
    assert await project_service.get_member_project(db_session, owner, project.id) is project
    assert await project_service.get_member_project(db_session, member, project.id) is project


@pytest.mark.parametrize(
    "action",
    [
        project_service.get_member_project,
        project_service.get_owned_project,
        project_service.delete_project,
    ],
    ids=["get", "get-owned", "delete"],
)
async def test_outsider_and_missing_project_are_not_found(
    db_session: AsyncSession,
    action: ProjectAction,
) -> None:
    """Non-members cannot tell a hidden project from a missing one."""
    project, owner, _, outsider = await make_team(db_session)
    with pytest.raises(NotFoundError, match=project_service.PROJECT_NOT_FOUND):
        await action(db_session, outsider, project.id)
    with pytest.raises(NotFoundError, match=project_service.PROJECT_NOT_FOUND):
        await action(db_session, owner, project.id + 1)


async def test_update_by_owner(db_session: AsyncSession) -> None:
    """Only sent fields change; the description can be cleared."""
    owner = await make_user(db_session, "owner@example.com")
    data = ProjectCreate(name="Alpha", description="Docs")
    project = await project_service.create_project(db_session, owner, data)
    changes = ProjectUpdate(description=None)
    updated = await project_service.update_project(db_session, owner, project.id, changes)
    assert updated.name == "Alpha"
    assert updated.description is None


@pytest.mark.parametrize(
    ("role", "error"),
    [("member", ForbiddenError), ("outsider", NotFoundError)],
)
async def test_update_by_non_owner_is_rejected(
    db_session: AsyncSession,
    role: str,
    error: type[DomainError],
) -> None:
    """A member gets 403, an outsider 404; the project is unchanged."""
    project, _, member, outsider = await make_team(db_session)
    user = member if role == "member" else outsider
    with pytest.raises(error):
        await project_service.update_project(
            db_session, user, project.id, ProjectUpdate(name="Hacked")
        )
    await db_session.refresh(project)
    assert project.name == "Alpha"


async def test_delete_by_owner(db_session: AsyncSession) -> None:
    """The owner deletes the project."""
    project, owner, _, _ = await make_team(db_session)
    await project_service.delete_project(db_session, owner, project.id)
    db_session.expunge_all()
    assert await project_repo.get_by_id(db_session, project.id) is None


async def test_delete_by_member_is_forbidden(db_session: AsyncSession) -> None:
    """A member gets 403 and the project stays."""
    project, _, member, _ = await make_team(db_session)
    with pytest.raises(ForbiddenError, match=project_service.OWNER_ONLY):
        await project_service.delete_project(db_session, member, project.id)
    assert await project_repo.get_by_id(db_session, project.id) is project
