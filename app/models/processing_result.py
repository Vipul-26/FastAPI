"""Processing result SQLAlchemy model — one result row per document."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.processing_job import ProcessingJobStatus

if TYPE_CHECKING:
    from app.models.document import Document


class ProcessingResult(Base):
    __tablename__ = "processing_results"

    # document_id is both FK and primary key (1:1 with documents)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[ProcessingJobStatus] = mapped_column(
        String(32),
        nullable=False,
    )

    document: Mapped[Document] = relationship(back_populates="processing_result")
