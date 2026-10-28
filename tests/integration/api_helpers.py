"""Shared helpers for API integration tests."""

from httpx import AsyncClient


async def register_and_login(client: AsyncClient, email: str = "ann@example.com") -> dict[str, str]:
    """Register a user and return its auth header.

    Parameters
    ----------
    client : AsyncClient
        Test client.
    email : str
        Email to register.

    Returns
    -------
    dict[str, str]
        ``Authorization`` header with a bearer token.
    """
    credentials = {"email": email, "password": "password123"}
    await client.post("/api/v1/auth/register", json={**credentials, "full_name": "Ann"})
    response = await client.post("/api/v1/auth/login", json=credentials)
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def get_user_id(client: AsyncClient, headers: dict[str, str]) -> int:
    """Return the id of the user behind an auth header.

    Parameters
    ----------
    client : AsyncClient
        Test client.
    headers : dict[str, str]
        ``Authorization`` header of the user.

    Returns
    -------
    int
        User identifier.
    """
    response = await client.get("/api/v1/users/me", headers=headers)
    return int(response.json()["id"])


async def make_team(
    client: AsyncClient,
) -> tuple[int, dict[str, str], dict[str, str], dict[str, str]]:
    """Create a project with an owner, a member and an outsider via the API.

    Parameters
    ----------
    client : AsyncClient
        Test client.

    Returns
    -------
    tuple[int, dict[str, str], dict[str, str], dict[str, str]]
        Project id and auth headers of the owner, member and outsider.
    """
    owner = await register_and_login(client, "owner@example.com")
    member = await register_and_login(client, "member@example.com")
    outsider = await register_and_login(client, "outsider@example.com")
    project = await client.post("/api/v1/projects", headers=owner, json={"name": "Alpha"})
    project_id = int(project.json()["id"])
    await client.post(
        f"/api/v1/projects/{project_id}/members",
        headers=owner,
        json={"user_id": await get_user_id(client, member)},
    )
    return project_id, owner, member, outsider
