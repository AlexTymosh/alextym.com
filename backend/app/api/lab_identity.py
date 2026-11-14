"""Private identity transport probe; contains no business or Fleet routes."""

from fastapi import APIRouter, Depends, Response

from app.security.firebase_identity import require_lab_identity

router = APIRouter(prefix="/lab", tags=["Portfolio Lab identity"])


@router.get("/identity", include_in_schema=False)
def check_identity(response: Response, identity: dict = Depends(require_lab_identity)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return identity
