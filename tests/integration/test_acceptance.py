"""Acceptance tests: end-to-end scenarios from the ТЗ, run through the HTTP API."""

from datetime import timedelta

from httpx import AsyncClient

from app._detail.helpers import utc_now
from tests.integration.api_helpers import get_user_id, register_and_login

PROJECTS = "/api/v1/projects"
TASKS = "/api/v1/tasks"
COMMENTS = "/api/v1/comments"


async def create_team(
    client: AsyncClient, prefix: str
) -> tuple[int, dict[str, str], dict[str, str], int]:
    """Register an owner and a member and put them in a new project.

    Parameters
    ----------
    client : AsyncClient
        Test client.
    prefix : str
        Distinguishes the emails and the project name of this team.

    Returns
    -------
    tuple[int, dict[str, str], dict[str, str], int]
        Project id, headers of the owner and the member, and the member's user id.
    """
    owner = await register_and_login(client, f"{prefix}-owner@example.com")
    member = await register_and_login(client, f"{prefix}-member@example.com")
    member_id = await get_user_id(client, member)
    project = await client.post(f"{PROJECTS}", headers=owner, json={"name": prefix})
    assert project.status_code == 201
    project_id = int(project.json()["id"])
    added = await client.post(
        f"{PROJECTS}/{project_id}/members", headers=owner, json={"user_id": member_id}
    )
    assert added.status_code == 201
    return project_id, owner, member, member_id


async def test_full_team_scenario(client: AsyncClient) -> None:
    """Owner builds a team, member works on a task, owner removes the member."""
    project_id, owner, member, member_id = await create_team(client, "alpha")
    members = await client.get(f"{PROJECTS}/{project_id}/members", headers=member)
    assert sorted(item["role"] for item in members.json()["items"]) == ["member", "owner"]
    task = await client.post(
        f"{PROJECTS}/{project_id}/tasks",
        headers=member,
        json={"title": "Write report", "assignee_id": member_id, "priority": "high"},
    )
    assert task.status_code == 201
    task_id = task.json()["id"]
    assert (task.json()["status"], task.json()["assignee_id"]) == ("todo", member_id)
    comment = await client.post(
        f"{TASKS}/{task_id}/comments", headers=member, json={"body": "Started"}
    )
    assert comment.status_code == 201
    for status in ("in_progress", "done"):
        updated = await client.patch(f"{TASKS}/{task_id}", headers=member, json={"status": status})
        assert (updated.status_code, updated.json()["status"]) == (200, status)
    seen = await client.get(f"{TASKS}/{task_id}", headers=owner)
    assert seen.json()["status"] == "done"
    comments = await client.get(f"{TASKS}/{task_id}/comments", headers=owner)
    assert [item["body"] for item in comments.json()["items"]] == ["Started"]
    removed = await client.delete(f"{PROJECTS}/{project_id}/members/{member_id}", headers=owner)
    assert removed.status_code == 204
    task_after = await client.get(f"{TASKS}/{task_id}", headers=owner)
    assert task_after.json()["assignee_id"] is None
    assert (await client.get(f"{PROJECTS}/{project_id}", headers=member)).status_code == 404
    assert (await client.get(f"{PROJECTS}/{project_id}/tasks", headers=member)).status_code == 404
    assert (await client.get(f"{TASKS}/{task_id}", headers=member)).status_code == 404
    assert (await client.get(f"{TASKS}/{task_id}/comments", headers=member)).status_code == 404
    comment_url = f"{COMMENTS}/{comment.json()['id']}"
    assert (await client.patch(comment_url, headers=member, json={"body": "X"})).status_code == 404
    assert (await client.get(PROJECTS, headers=member)).json()["total"] == 0


async def test_two_teams_are_isolated(client: AsyncClient) -> None:
    """Neither team can see, change or join the other team's resources."""
    alpha_id, alpha_owner, _, alpha_member_id = await create_team(client, "alpha")
    beta_id, beta_owner, beta_member, _ = await create_team(client, "beta")
    alpha_task = await client.post(
        f"{PROJECTS}/{alpha_id}/tasks", headers=alpha_owner, json={"title": "Secret"}
    )
    alpha_task_id = alpha_task.json()["id"]
    alpha_comment = await client.post(
        f"{TASKS}/{alpha_task_id}/comments", headers=alpha_owner, json={"body": "Private"}
    )
    listed = await client.get(PROJECTS, headers=beta_member)
    assert [item["id"] for item in listed.json()["items"]] == [beta_id]
    for headers in (beta_owner, beta_member):
        assert (await client.get(f"{PROJECTS}/{alpha_id}", headers=headers)).status_code == 404
        response = await client.get(f"{PROJECTS}/{alpha_id}/members", headers=headers)
        assert response.status_code == 404
        response = await client.get(f"{PROJECTS}/{alpha_id}/tasks", headers=headers)
        assert response.status_code == 404
        response = await client.post(
            f"{PROJECTS}/{alpha_id}/tasks", headers=headers, json={"title": "Intrude"}
        )
        assert response.status_code == 404
        response = await client.patch(
            f"{TASKS}/{alpha_task_id}", headers=headers, json={"status": "done"}
        )
        assert response.status_code == 404
        assert (await client.delete(f"{TASKS}/{alpha_task_id}", headers=headers)).status_code == 404
        response = await client.get(f"{TASKS}/{alpha_task_id}/comments", headers=headers)
        assert response.status_code == 404
        response = await client.delete(f"{COMMENTS}/{alpha_comment.json()['id']}", headers=headers)
        assert response.status_code == 404
    response = await client.post(
        f"{PROJECTS}/{beta_id}/tasks",
        headers=beta_owner,
        json={"title": "Borrow", "assignee_id": alpha_member_id},
    )
    assert response.status_code == 422
    unchanged = await client.get(f"{TASKS}/{alpha_task_id}", headers=alpha_owner)
    assert unchanged.json()["status"] == "todo"


async def test_owner_and_member_rights(client: AsyncClient) -> None:
    """Only the owner manages the project and its members; members manage tasks."""
    project_id, owner, member, member_id = await create_team(client, "alpha")
    owner_id = await get_user_id(client, owner)
    newcomer = await register_and_login(client, "newcomer@example.com")
    newcomer_id = await get_user_id(client, newcomer)
    project_url = f"{PROJECTS}/{project_id}"
    members_url = f"{project_url}/members"
    assert (await client.patch(project_url, headers=member, json={"name": "X"})).status_code == 403
    assert (await client.delete(project_url, headers=member)).status_code == 403
    response = await client.post(members_url, headers=member, json={"user_id": newcomer_id})
    assert response.status_code == 403
    assert (await client.delete(f"{members_url}/{owner_id}", headers=member)).status_code == 403
    response = await client.post(members_url, headers=owner, json={"user_id": member_id})
    assert response.status_code == 409
    assert (await client.delete(f"{members_url}/{owner_id}", headers=owner)).status_code == 409
    response = await client.post(members_url, headers=owner, json={"user_id": newcomer_id + 100})
    assert response.status_code == 404
    task = await client.post(f"{project_url}/tasks", headers=owner, json={"title": "Owner's"})
    task_url = f"{TASKS}/{task.json()['id']}"
    edited = await client.patch(task_url, headers=member, json={"title": "Edited by member"})
    assert (edited.status_code, edited.json()["title"]) == (200, "Edited by member")
    assert (await client.delete(task_url, headers=member)).status_code == 204
    renamed = await client.patch(project_url, headers=owner, json={"name": "Renamed"})
    assert (renamed.status_code, renamed.json()["name"]) == (200, "Renamed")


async def test_assignee_must_be_current_member(client: AsyncClient) -> None:
    """Outsiders and removed members cannot be assignees; nothing is stored on 422."""
    project_id, owner, _, member_id = await create_team(client, "alpha")
    outsider_id = await get_user_id(client, await register_and_login(client, "out@example.com"))
    tasks_url = f"{PROJECTS}/{project_id}/tasks"
    response = await client.post(
        tasks_url, headers=owner, json={"title": "X", "assignee_id": outsider_id}
    )
    assert response.status_code == 422
    task = await client.post(tasks_url, headers=owner, json={"title": "Y"})
    task_url = f"{TASKS}/{task.json()['id']}"
    response = await client.patch(task_url, headers=owner, json={"assignee_id": outsider_id})
    assert response.status_code == 422
    await client.delete(f"{PROJECTS}/{project_id}/members/{member_id}", headers=owner)
    response = await client.patch(task_url, headers=owner, json={"assignee_id": member_id})
    assert response.status_code == 422
    assert (await client.get(task_url, headers=owner)).json()["assignee_id"] is None
    assert (await client.get(tasks_url, headers=owner)).json()["total"] == 1


async def test_filters_and_overdue(client: AsyncClient) -> None:
    """Filters combine; overdue means past ``due_at`` and not done."""
    project_id, owner, member, member_id = await create_team(client, "alpha")
    tasks_url = f"{PROJECTS}/{project_id}/tasks"
    past = (utc_now() - timedelta(days=1)).isoformat()
    future = (utc_now() + timedelta(days=1)).isoformat()
    specs = [
        {"title": "late", "due_at": past, "assignee_id": member_id, "priority": "high"},
        {"title": "late-done", "due_at": past, "status": "done"},
        {"title": "on-time", "due_at": future, "assignee_id": member_id},
        {"title": "no-date", "priority": "high"},
    ]
    for spec in specs:
        assert (await client.post(tasks_url, headers=owner, json=spec)).status_code == 201
    cases: list[tuple[dict[str, str], list[str]]] = [
        ({"overdue": "true"}, ["late"]),
        ({"overdue": "false"}, ["late-done", "no-date", "on-time"]),
        ({"assignee_id": str(member_id)}, ["late", "on-time"]),
        ({"priority": "high", "overdue": "false"}, ["no-date"]),
        ({"status": "done"}, ["late-done"]),
        ({"status": "todo", "assignee_id": str(member_id), "overdue": "true"}, ["late"]),
    ]
    for params, expected in cases:
        response = await client.get(tasks_url, headers=member, params=params)
        assert response.status_code == 200
        assert sorted(item["title"] for item in response.json()["items"]) == expected
    page = await client.get(
        tasks_url, headers=member, params={"sort": "id", "order": "asc", "limit": 2, "offset": 1}
    )
    body = page.json()
    assert ([item["title"] for item in body["items"]], body["total"]) == (
        ["late-done", "on-time"],
        4,
    )


async def test_account_and_project_deletion(client: AsyncClient) -> None:
    """Owners must delete projects first; deletions cascade and unassign tasks."""
    project_id, owner, member, member_id = await create_team(client, "alpha")
    task = await client.post(
        f"{PROJECTS}/{project_id}/tasks",
        headers=owner,
        json={"title": "X", "assignee_id": member_id},
    )
    task_url = f"{TASKS}/{task.json()['id']}"
    comment = await client.post(f"{task_url}/comments", headers=owner, json={"body": "Hi"})
    assert (await client.delete("/api/v1/users/me", headers=owner)).status_code == 409
    assert (await client.delete("/api/v1/users/me", headers=member)).status_code == 204
    assert (await client.get(task_url, headers=owner)).json()["assignee_id"] is None
    assert (await client.delete(f"{PROJECTS}/{project_id}", headers=owner)).status_code == 204
    assert (await client.get(task_url, headers=owner)).status_code == 404
    comment_url = f"{COMMENTS}/{comment.json()['id']}"
    assert (await client.patch(comment_url, headers=owner, json={"body": "X"})).status_code == 404
    assert (await client.delete("/api/v1/users/me", headers=owner)).status_code == 204
