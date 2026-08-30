"""Document routes — CRUD with ownership (user_id from JWT, never from client)."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_user,
    get_owned_document,
    get_owned_document_sse,
)
from app.db.database import get_db
from app.models.document import Document
from app.models.processing_job import ProcessingJob
from app.models.processing_result import ProcessingResult
from app.models.user import User
from app.schemas.document import DocumentCreate, DocumentResponse, DocumentUpdate
from app.schemas.job import ProcessingResultResponse
from app.services.event_bus import document_event_bus
from app.services.processing import process_document_job
from app.services.sse import build_status_event, document_event_stream

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    document_in: DocumentCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Create a document owned by the authenticated user."""
    document = Document(
        title=document_in.title,
        content=document_in.content,
        user_id=current_user.id,  # from JWT — client cannot set owner
    )
    db.add(document)
    await db.flush()  # assign document.id before creating the job

    job = ProcessingJob(document_id=document.id)
    db.add(job)
    await db.commit()
    await db.refresh(document)

    await document_event_bus.publish(
        document.id,
        build_status_event(
            document.id,
            "queued",
            job_id=str(job.id),
            job_status="queued",
        ),
    )

    background_tasks.add_task(process_document_job, job.id)

    return document


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """Return documents owned by the authenticated user only."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{document_id}/events")
async def stream_document_events(
    document: Document = Depends(get_owned_document_sse),
) -> StreamingResponse:
    """SSE stream of document processing status (queued → processing → completed)."""
    return StreamingResponse(
        document_event_stream(document.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{document_id}/result", response_model=ProcessingResultResponse)
async def get_document_result(
    document: Document = Depends(get_owned_document),
    db: AsyncSession = Depends(get_db),
) -> ProcessingResultResponse:
    """Return processing result for a document (after job completes)."""
    result = await db.execute(
        select(ProcessingResult).where(ProcessingResult.document_id == document.id)
    )
    processing_result = result.scalar_one_or_none()

    if processing_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing result not ready yet",
        )

    return processing_result


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document: Document = Depends(get_owned_document),
) -> DocumentResponse:
    """Return one document if it exists and belongs to the current user."""
    return document


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_in: DocumentUpdate,
    document: Document = Depends(get_owned_document),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Partially update a document (only fields sent in the body are changed)."""
    for field, value in document_in.model_dump(exclude_unset=True).items():
        setattr(document, field, value)

    await db.commit()
    await db.refresh(document)

    return document


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document: Document = Depends(get_owned_document),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a document if it belongs to the current user."""
    await db.delete(document)
    await db.commit()
