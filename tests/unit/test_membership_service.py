"""Unit tests for ``app.services.membership``."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import MembershipRole, Task
from app.repositories import membership as membership_repo
from app.schemas.common import PageParams
from app.schemas.project import MemberCreate
from app.services import membership as membership_service
from app.services import project as project_service
from tests.unit.service_helpers import make_team


async def test_list_members_for_member(db_session: AsyncSession) -> None:
    """Any member sees all members, newest first."""
    project, owner, member, _ = await make_team(db_session)
    items, total = await membership_service.list_members(
        db_session, member, project.id, PageParams()
    )
    assert [item.user_id for item in items] == [member.id, owner.id]
    assert total == 2


async def test_list_members_hidden_from_outsider(db_session: AsyncSession) -> None:
    """A non-member gets 404 for the member list."""
    project, _, _, outsider = await make_team(db_session)
    with pytest.raises(NotFoundError, match=project_service.PROJECT_NOT_FOUND):
        await membership_service.list_members(db_session, outsider, project.id, PageParams())


async def test_add_member_by_owner(db_session: AsyncSession) -> None:
    """The owner adds a registered user with the ``member`` role."""
    project, owner, _, outsider = await make_team(db_session)
    membership = await membership_service.add_member(
        db_session, owner, project.id, MemberCreate(user_id=outsider.id)
    )
    assert membership.role == MembershipRole.MEMBER
    assert await project_service.get_member_project(db_session, outsider, project.id) is project


async def test_add_member_rejects_non_owner(db_session: AsyncSession) -> None:
    """A member gets 403, an outsider 404."""
    project, _, member, outsider = await make_team(db_session)
    data = MemberCreate(user_id=outsider.id)
    with pytest.raises(ForbiddenError):
        await membership_service.add_member(db_session, member, project.id, data)
    with pytest.raises(NotFoundError, match=project_service.PROJECT_NOT_FOUND):
        await membership_service.add_member(db_session, outsider, project.id, data)


async def test_add_missing_user_is_not_found(db_session: AsyncSession) -> None:
    """Only registered users can be added."""
    project, owner, _, _ = await make_team(db_session)
    with pytest.raises(NotFoundError, match=membership_service.USER_NOT_FOUND):
        await membership_service.add_member(
            db_session, owner, project.id, MemberCreate(user_id=999)
        )


async def test_add_existing_member_conflicts(db_session: AsyncSession) -> None:
    """Adding a current member (or the owner) gives 409."""
    project, owner, member, _ = await make_team(db_session)
    for user_id in (member.id, owner.id):
        with pytest.raises(ConflictError, match=membership_service.ALREADY_MEMBER):
            await membership_service.add_member(
                db_session, owner, project.id, MemberCreate(user_id=user_id)
            )


async def test_add_member_race_maps_integrity_error_to_conflict(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A duplicate missed by the pre-check is still reported as 409."""
    project, owner, member, _ = await make_team(db_session)
    owner_membership = await membership_repo.get(db_session, project.id, owner.id)
    # First call: owner access check; second call: duplicate pre-check misses.
    monkeypatch.setattr(membership_repo, "get", AsyncMock(side_effect=[owner_membership, None]))
    with pytest.raises(ConflictError, match=membership_service.ALREADY_MEMBER):
        await membership_service.add_member(
            db_session, owner, project.id, MemberCreate(user_id=member.id)
        )


async def test_remove_member_unassigns_tasks_and_revokes_access(db_session: AsyncSession) -> None:
    """The removed member loses access; only their tasks lose the assignee."""
    project, owner, member, _ = await make_team(db_session)
    member_task = Task(project_id=project.id, title="member", assignee_id=member.id)
    owner_task = Task(project_id=project.id, title="owner", assignee_id=owner.id)
    db_session.add_all([member_task, owner_task])
    await db_session.commit()
    await membership_service.remove_member(db_session, owner, project.id, member.id)
    await db_session.refresh(member_task)
    await db_session.refresh(owner_task)
    assert member_task.assignee_id is None
    assert owner_task.assignee_id == owner.id
    with pytest.raises(NotFoundError, match=project_service.PROJECT_NOT_FOUND):
        await project_service.get_member_project(db_session, member, project.id)


async def test_owner_cannot_remove_self(db_session: AsyncSession) -> None:
    """The owner leaves only by deleting the project (409)."""
    project, owner, _, _ = await make_team(db_session)
    with pytest.raises(ConflictError, match=membership_service.OWNER_NOT_REMOVABLE):
        await membership_service.remove_member(db_session, owner, project.id, owner.id)
    assert await membership_repo.get(db_session, project.id, owner.id) is not None


async def test_remove_non_member_is_not_found(db_session: AsyncSession) -> None:
    """Removing a user who is not a member gives 404."""
    project, owner, _, outsider = await make_team(db_session)
    with pytest.raises(NotFoundError, match=membership_service.MEMBER_NOT_FOUND):
        await membership_service.remove_member(db_session, owner, project.id, outsider.id)


async def test_remove_member_rejects_non_owner(db_session: AsyncSession) -> None:
    """A member gets 403, an outsider 404; the membership stays."""
    project, owner, member, outsider = await make_team(db_session)
    with pytest.raises(ForbiddenError):
        await membership_service.remove_member(db_session, member, project.id, member.id)
    with pytest.raises(NotFoundError, match=project_service.PROJECT_NOT_FOUND):
        await membership_service.remove_member(db_session, outsider, project.id, member.id)
    assert await membership_repo.get(db_session, project.id, member.id) is not None
