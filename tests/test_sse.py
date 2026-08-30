"""SSE streaming tests (Step 10.9)."""

import json

import httpx
import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, unique_email, wait_for_job


async def collect_sse_events(
    client: AsyncClient,
    url: str,
    headers: dict[str, str] | None = None,
) -> list[dict]:
    events: list[dict] = []
    try:
        async with client.stream("GET", url, headers=headers) as response:
            assert response.status_code == 200
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    for line in frame.splitlines():
                        if line.startswith("data:"):
                            events.append(json.loads(line[5:].strip()))
    except httpx.RemoteProtocolError:
        pass
    return events


@pytest.mark.asyncio
async def test_sse_requires_auth(client: AsyncClient) -> None:
    doc_id = "00000000-0000-0000-0000-000000000001"
    response = await client.get(f"/api/v1/documents/{doc_id}/events")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sse_completed_snapshot(auth_client: dict) -> None:
    client = auth_client["client"]
    headers = auth_client["headers"]

    created = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={"title": "SSE", "content": "one two"},
    )
    doc_id = created.json()["id"]

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

    await wait_for_job(client, job_id, headers)

    events = await collect_sse_events(
        client,
        f"/api/v1/documents/{doc_id}/events",
        headers,
    )
    assert events
    assert events[-1]["status"] == "completed"
    assert events[-1]["word_count"] == 2


@pytest.mark.asyncio
async def test_sse_query_token_auth(auth_client: dict) -> None:
    client = auth_client["client"]
    headers = auth_client["headers"]
    token = auth_client["token"]

    created = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={"title": "SSE token", "content": "hello"},
    )
    doc_id = created.json()["id"]

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

    await wait_for_job(client, job_id, headers)

    events = await collect_sse_events(
        client,
        f"/api/v1/documents/{doc_id}/events?access_token={token}",
    )
    assert events
    assert events[-1]["status"] == "completed"
