"""Authentication and authorization tests (Step 10.7)."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user, unique_email


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    email = unique_email("auth")
    password = "StrongPassword123"

    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert register.status_code == 201
    user = register.json()
    assert user["email"] == email
    assert "id" in user
    assert "password" not in user
    assert "password_hash" not in user

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    email = unique_email("badlogin")
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPassword123"},
    )

    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword123"},
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["error_type"] == "unauthorized"

    unknown_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "StrongPassword123"},
    )
    assert unknown_email.status_code == 401
    assert unknown_email.json()["detail"] == wrong_password.json()["detail"]


@pytest.mark.asyncio
async def test_users_me_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_users_me_returns_current_user(auth_client: dict) -> None:
    client = auth_client["client"]
    response = await client.get("/api/v1/users/me", headers=auth_client["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == auth_client["email"]
    assert body["id"] == auth_client["user"]["id"]


@pytest.mark.asyncio
async def test_invalid_token_rejected(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/users/me",
        headers=auth_headers("not.a.valid.jwt"),
    )
    assert response.status_code == 401
