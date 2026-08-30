"""Pydantic schemas for processing jobs and results (Step 8 — routes not wired yet)."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProcessingJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJobResponse(BaseModel):
    """Status of a background processing job for a document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    status: ProcessingJobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class ProcessingResultResponse(BaseModel):
    """Output of document processing (word/character counts)."""

    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    word_count: int
    character_count: int
    processed_at: datetime
    status: ProcessingJobStatus
