"""Background document processing — word/character counts."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.document import Document, DocumentStatus
from app.models.processing_job import ProcessingJob, ProcessingJobStatus
from app.models.processing_result import ProcessingResult
from app.services.event_bus import document_event_bus
from app.services.sse import build_status_event


def count_words(text: str) -> int:
    """Count whitespace-separated words."""
    stripped = text.strip()
    if not stripped:
        return 0
    return len(stripped.split())


def count_characters(text: str) -> int:
    """Count all characters in the content string."""
    return len(text)


async def process_document_job(job_id: UUID) -> None:
    """Run async processing for a queued job (uses its own DB session)."""
    async with AsyncSessionLocal() as db:
        try:
            job = (
                await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
            ).scalar_one_or_none()
            if job is None:
                return

            document = (
                await db.execute(select(Document).where(Document.id == job.document_id))
            ).scalar_one()

            job.status = ProcessingJobStatus.PROCESSING
            job.started_at = datetime.now(UTC)
            document.status = DocumentStatus.PROCESSING
            await db.commit()

            await document_event_bus.publish(
                document.id,
                build_status_event(
                    document.id,
                    DocumentStatus.PROCESSING.value,
                    job_id=str(job.id),
                    job_status=ProcessingJobStatus.PROCESSING.value,
                ),
            )

            word_count = count_words(document.content)
            character_count = count_characters(document.content)

            db.add(
                ProcessingResult(
                    document_id=document.id,
                    word_count=word_count,
                    character_count=character_count,
                    status=ProcessingJobStatus.COMPLETED,
                )
            )
            job.status = ProcessingJobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
            document.status = DocumentStatus.COMPLETED
            await db.commit()

            await document_event_bus.publish(
                document.id,
                build_status_event(
                    document.id,
                    DocumentStatus.COMPLETED.value,
                    job_id=str(job.id),
                    job_status=ProcessingJobStatus.COMPLETED.value,
                    word_count=word_count,
                    character_count=character_count,
                ),
            )
        except Exception as exc:
            await db.rollback()
            async with AsyncSessionLocal() as fail_db:
                job = (
                    await fail_db.execute(
                        select(ProcessingJob).where(ProcessingJob.id == job_id)
                    )
                ).scalar_one_or_none()
                if job is None:
                    return

                job.status = ProcessingJobStatus.FAILED
                job.completed_at = datetime.now(UTC)
                job.error = str(exc)

                document = (
                    await fail_db.execute(
                        select(Document).where(Document.id == job.document_id)
                    )
                ).scalar_one_or_none()
                if document is not None:
                    document.status = DocumentStatus.FAILED

                await fail_db.commit()

                if document is not None:
                    await document_event_bus.publish(
                        document.id,
                        build_status_event(
                            document.id,
                            DocumentStatus.FAILED.value,
                            job_id=str(job.id),
                            job_status=ProcessingJobStatus.FAILED.value,
                            error=str(exc),
                        ),
                    )
