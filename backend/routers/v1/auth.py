"""Auth routes — login info, profile."""

from fastapi import APIRouter, Depends
from middleware.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/auth")


@router.get("/me")
async def get_me(user: CurrentUser = Depends(get_current_user)):
    """Return the authenticated user's info from JWT."""
    return {"id": user.id, "email": user.email, "role": user.role}
