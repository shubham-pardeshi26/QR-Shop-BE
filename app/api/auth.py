"""Auth endpoints — verify the Supabase token and expose the caller's profile."""
from fastapi import APIRouter

from app.core.deps import CurrentProfile
from app.schemas.auth import ProfileOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=ProfileOut)
def me(profile: CurrentProfile) -> ProfileOut:
    """Return the authenticated staff/admin user's profile."""
    return ProfileOut.model_validate(profile)
