"""Host-owned SP01 feature flag and existing Portfolio Lab access adapter."""

import os

from fastapi import HTTPException, Request

from app.security.project_grants import require_project_access


def require_sameplace_member(request: Request) -> None:
    # The disabled route is closed before identity or provider access.
    if os.getenv("PORTFOLIO_LAB_ENABLED") != "true" or os.getenv("SAMEPLACE_ENABLED") != "true":
        raise HTTPException(404, "Not found")
    require_project_access(request, "sameplace")
