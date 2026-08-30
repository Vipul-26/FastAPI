"""Document CRUD and processing tests (Step 10.8)."""

import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, register_user, unique_email, wait_for_job


@pytest.mark.asyncio
async def test_create_and_list_documents(auth_client: dict) -> None:
    client = auth_client["client"]
    headers = auth_client["headers"]

    created = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={"title": "Notes", "content": "hello world"},
    )
    assert created.status_code == 201
    doc = created.json()
    assert doc["title"] == "Notes"
    assert doc["content"] == "hello world"
    assert "id" in doc

    listed = await client.get("/api/v1/documents", headers=headers)
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()]
    assert doc["id"] in ids


@pytest.mark.asyncio
async def test_list_documents_isolated_per_user(client: AsyncClient) -> None:
    user_a = await register_user(client, unique_email("lista"))
    token_a = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": user_a["email"], "password": user_a["password"]},
        )
    ).json()["access_token"]

    user_b = await register_user(client, unique_email("listb"))
    token_b = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": user_b["email"], "password": user_b["password"]},
        )
    ).json()["access_token"]

    await client.post(
        "/api/v1/documents",
        headers=auth_headers(token_a),
        json={"title": "A only", "content": "alpha"},
    )

    list_b = await client.get("/api/v1/documents", headers=auth_headers(token_b))
    assert list_b.status_code == 200
    assert list_b.json() == []


@pytest.mark.asyncio
async def test_get_patch_delete_document(auth_client: dict) -> None:
    client = auth_client["client"]
    headers = auth_client["headers"]

    created = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={"title": "Draft", "content": "first version"},
    )
    doc_id = created.json()["id"]

    fetched = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Draft"

    patched = await client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=headers,
        json={"title": "Final"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "Final"
    assert patched.json()["content"] == "first version"

    deleted = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_processing_job_and_result(auth_client: dict) -> None:
    client = auth_client["client"]
    headers = auth_client["headers"]

    created = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={"title": "Counts", "content": "one two three"},
    )
    assert created.status_code == 201
    doc_id = created.json()["id"]

    not_ready = await client.get(
        f"/api/v1/documents/{doc_id}/result",
        headers=headers,
    )
    # May be 404 while processing or 200 if background task already finished
    assert not_ready.status_code in {404, 200}

    jobs = await client.get("/api/v1/documents", headers=headers)
    assert jobs.status_code == 200

    # Fetch job via documents list is indirect; query job from DB via jobs endpoint
    # by listing documents and using the processing job created on POST.
    from sqlalchemy import select

    from app.db.database import AsyncSessionLocal
    from app.models.processing_job import ProcessingJob

    async with AsyncSessionLocal() as db:
        job = (
            await db.execute(
                select(ProcessingJob).where(ProcessingJob.document_id == doc_id)
            )
        ).scalar_one()
        job_id = str(job.id)

    completed = await wait_for_job(client, job_id, headers)
    assert completed["status"] == "completed"

    result = await client.get(
        f"/api/v1/documents/{doc_id}/result",
        headers=headers,
    )
    assert result.status_code == 200
    body = result.json()
    assert body["word_count"] == 3
    assert body["character_count"] == len("one two three")
