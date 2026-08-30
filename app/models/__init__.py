"""SQLAlchemy models — database tables (the persistence layer).

These define PostgreSQL tables. API request/response shapes live in app/schemas/.
Alembic reads Base.metadata from these models to generate migrations.
"""

from app.models.document import Document
from app.models.processing_job import ProcessingJob
from app.models.processing_result import ProcessingResult
from app.models.user import User

__all__ = ["User", "Document", "ProcessingJob", "ProcessingResult"]
