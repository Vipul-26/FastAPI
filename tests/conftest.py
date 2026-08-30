"""Shared pytest fixtures for API integration tests (Step 10.5)."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from uuid import uuid4

# Must be set before app/database import so tests use NullPool connections.
os.environ["PYTEST_RUNNING"] = "1"

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(scope="session")
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP client wired to the FastAPI app (no live server needed)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def drain_background_tasks() -> AsyncIterator[None]:
    """Let FastAPI background tasks finish before the next test starts."""
    yield
    await asyncio.sleep(0.15)


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid4().hex[:10]}@example.com"


async def register_user(
    client: AsyncClient,
    email: str | None = None,
    password: str = "StrongPassword123",
) -> dict:
    email = email or unique_email()
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201
    return {"email": email, "password": password, "user": response.json()}


async def login_user(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_client(client: AsyncClient) -> dict:
    """Register a user, log in, and return client + token + user payload."""
    account = await register_user(client)
    token = await login_user(client, account["email"], account["password"])
    return {
        "client": client,
        "token": token,
        "headers": auth_headers(token),
        "email": account["email"],
        "password": account["password"],
        "user": account["user"],
    }


async def wait_for_job(
    client: AsyncClient,
    job_id: str,
    headers: dict[str, str],
    *,
    expected: str = "completed",
    timeout: float = 5.0,
) -> dict:
    """Poll job status until it reaches the expected terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] == expected:
            return payload
        await asyncio.sleep(0.1)
    raise AssertionError(f"Job {job_id} did not reach status {expected!r}")
