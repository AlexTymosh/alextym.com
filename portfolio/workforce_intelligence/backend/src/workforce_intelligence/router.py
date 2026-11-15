"""Project-owned HTTP router. Host applies shared Firebase grant dependency.

This package must not import website security implementations or other projects.
Every project route is mounted with `require_workforce_member` by the host.
"""

from fastapi import APIRouter, Response

router = APIRouter(prefix="/workforce", tags=["Workforce Intelligence"])


@router.get("/status", include_in_schema=False)
def workforce_status(response: Response) -> dict[str, bool | str]:
    response.headers["Cache-Control"] = "no-store"
    return {"service": "workforce", "available": True}
