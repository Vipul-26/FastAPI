"""Consistent error response schema (Step 10.3)."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard JSON body for API errors."""

    detail: str | list[dict[str, Any]]
    error_type: str = Field(
        description="Machine-readable error category",
    )
