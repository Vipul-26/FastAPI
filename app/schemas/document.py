"""Pydantic schemas for document API (Step 7 — routes not wired yet).

These validate JSON in/out. The database table is app.models.document.Document.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentStatus(str, Enum):
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentCreate(BaseModel):
    """Request body to create a new document."""

    title: str = Field(
        min_length=1,
        max_length=200,
    )
    content: str = Field(
        min_length=1,
        max_length=1_000_000,
    )


class DocumentUpdate(BaseModel):
    """Request body to partially update a document (all fields optional)."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=1_000_000,
    )


class DocumentResponse(BaseModel):
    """Document returned to the client (no user_id in response for now)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    content: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
