"""Server-Sent Events helpers for document processing."""

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.document import Document
from app.models.processing_job import ProcessingJob
from app.models.processing_result import ProcessingResult
from app.services.event_bus import TERMINAL_STATUSES, document_event_bus


def _status_value(status: object) -> str:
    return status.value if hasattr(status, "value") else str(status)


def build_status_event(document_id: UUID, status: str, **extra: object) -> dict[str, object]:
    """Build a JSON-serializable SSE payload."""
    payload: dict[str, object] = {
        "document_id": str(document_id),
        "status": status,
    }
    payload.update(extra)
    return payload


def format_sse(event: dict[str, object], event_type: str = "status") -> str:
    """Format one Server-Sent Event frame."""
    return f"event: {event_type}\ndata: {json.dumps(event)}\n\n"


async def snapshot_event(db: AsyncSession, document_id: UUID) -> dict[str, object] | None:
    """Build the latest status event from PostgreSQL (for late subscribers)."""
    document = (
        await db.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if document is None:
        return None

    status = _status_value(document.status)

    job = (
        await db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.document_id == document_id)
            .order_by(ProcessingJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if job is not None and status not in TERMINAL_STATUSES:
        status = _status_value(job.status)

    event = build_status_event(document_id, status)

    if job is not None:
        event["job_id"] = str(job.id)
        event["job_status"] = _status_value(job.status)

    if status in TERMINAL_STATUSES:
        result = (
            await db.execute(
                select(ProcessingResult).where(ProcessingResult.document_id == document_id)
            )
        ).scalar_one_or_none()
        if result is not None:
            event["word_count"] = result.word_count
            event["character_count"] = result.character_count
        if job is not None and job.error:
            event["error"] = job.error

    return event


async def document_event_stream(document_id: UUID) -> AsyncIterator[str]:
    """Yield SSE frames for a document until processing reaches a terminal state."""
    last_status: object | None = None

    async with AsyncSessionLocal() as db:
        current = await snapshot_event(db, document_id)
        if current is None:
            return

        yield format_sse(current)
        last_status = current.get("status")
        if last_status in TERMINAL_STATUSES:
            return

    queue_iter = document_event_bus.subscribe(document_id).__aiter__()
    while True:
        try:
            live_event = await asyncio.wait_for(queue_iter.__anext__(), timeout=1.0)
        except TimeoutError:
            async with AsyncSessionLocal() as db:
                current = await snapshot_event(db, document_id)
                if current is None:
                    break
                status = current.get("status")
                if status != last_status:
                    yield format_sse(current)
                    last_status = status
                if status in TERMINAL_STATUSES:
                    break
            continue
        except StopAsyncIteration:
            break

        yield format_sse(live_event)
        last_status = live_event.get("status")
        if last_status in TERMINAL_STATUSES:
            break
