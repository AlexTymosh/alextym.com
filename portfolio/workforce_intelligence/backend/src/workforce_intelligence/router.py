"""Public API entry point. Intentionally fail-closed until project RBAC is added.

The project is registered and installed, but neither a Firebase identity nor a
feature flag authorizes the application. Commit 02 will replace this closed
stub with a shared Portfolio Lab authorization dependency.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/workforce", tags=["Workforce Intelligence"])


@router.get("/status", include_in_schema=False)
def denied_until_project_grants() -> None:
    """Allow no users or data until cross-host grant verification exists."""
    raise HTTPException(status_code=404, detail="Not found")
