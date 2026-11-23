"""Host-owned Firebase project grant adapter; no trust in page access alone."""

import os

from fastapi import HTTPException, Request

from app.security.project_grants import require_project_access


def require_preferans_member(request: Request) -> None:
    if (
        os.getenv("PORTFOLIO_LAB_ENABLED") != "true"
        or os.getenv("PREFERANS_ROOMS_ENABLED") != "true"
    ):
        raise HTTPException(404, "Not found")
    identity = require_project_access(request, "preferans")
    request.state.preferans_uid = identity["uid"]
    request.state.preferans_owner = (
        identity["uid"] == os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
    )
