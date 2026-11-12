"""Private identity transport probe; contains no business or Fleet routes."""

from fastapi import APIRouter, Depends

from app.security.firebase_identity import require_owner_identity

router = APIRouter(prefix="/lab", tags=["Portfolio Lab identity"])


@router.get("/identity", include_in_schema=False)
def check_identity(identity: dict = Depends(require_owner_identity)) -> dict:
    return identity
