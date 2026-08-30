"""User routes — protected endpoints for the authenticated user."""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the currently logged-in user (requires Bearer JWT).

    The endpoint does NOT decode the JWT itself — get_current_user does that.
    UserResponse ensures password_hash is never sent to the client.
    """
    return current_user
