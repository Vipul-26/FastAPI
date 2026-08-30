"""Validation and global error response tests (Step 10.1–10.3)."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user, unique_email


@pytest.mark.asyncio
async def test_validation_error_shape(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "short"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "validation_error"
    assert isinstance(body["detail"], list)
    assert body["detail"]


@pytest.mark.asyncio
async def test_http_exception_includes_error_type(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
    body = response.json()
    assert body["error_type"] == "unauthorized"
    assert body["detail"] == "Invalid or expired credentials"


@pytest.mark.asyncio
async def test_register_conflict_status_code(client: AsyncClient) -> None:
    email = unique_email("conflict")
    first = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPassword123"},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "StrongPassword123"},
    )
    assert second.status_code == 409
    body = second.json()
    assert body["error_type"] == "conflict"
    assert body["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_document_not_found_returns_404(auth_client: dict) -> None:
    client = auth_client["client"]
    headers = auth_client["headers"]
    missing_id = "00000000-0000-0000-0000-000000000099"
    response = await client.get(f"/api/v1/documents/{missing_id}", headers=headers)
    assert response.status_code == 404
    assert response.json()["error_type"] == "not_found"


@pytest.mark.asyncio
async def test_document_forbidden_returns_403(client: AsyncClient) -> None:
    owner = await register_user(client, unique_email("owner"))
    owner_token = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": owner["email"], "password": owner["password"]},
        )
    ).json()["access_token"]

    other = await register_user(client, unique_email("other"))
    other_token = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": other["email"], "password": other["password"]},
        )
    ).json()["access_token"]

    doc = await client.post(
        "/api/v1/documents",
        headers=auth_headers(owner_token),
        json={"title": "Private", "content": "secret"},
    )
    doc_id = doc.json()["id"]

    response = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_headers(other_token),
    )
    assert response.status_code == 403
    assert response.json()["error_type"] == "forbidden"
