"""Pydantic schemas for user API contracts (not database tables).

UserCreate  — request body for registration (includes password)
UserResponse — safe response (id, email, created_at — no password)
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.networks import EmailStr


class UserCreate(BaseModel):
    """Validated input when a client registers."""

    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
        description="User password",
    )


class UserResponse(BaseModel):
    """What the API returns about a user — never includes password_hash."""

    model_config = ConfigDict(from_attributes=True)  # build from SQLAlchemy User

    id: UUID
    email: EmailStr
    created_at: datetime
