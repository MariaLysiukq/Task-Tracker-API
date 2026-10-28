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
