"""Processing job routes — track async document processing."""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_owned_job
from app.models.processing_job import ProcessingJob
from app.schemas.job import ProcessingJobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=ProcessingJobResponse)
async def get_job(
    job: ProcessingJob = Depends(get_owned_job),
) -> ProcessingJobResponse:
    """Return processing job status for a document owned by the current user."""
    return job
