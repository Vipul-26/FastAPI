"""Pydantic schemas for login and JWT token responses."""

from pydantic import BaseModel, Field
from pydantic.networks import EmailStr


class LoginRequest(BaseModel):
    """Validated input for POST /auth/login."""

    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class TokenResponse(BaseModel):
    """JWT returned after successful login."""

    access_token: str
    token_type: str = "bearer"
