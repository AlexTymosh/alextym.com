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


def verify_preferans_realtime(authorization: str) -> tuple[str, bool]:
    """Re-use host identity/admission/grant checks for a redeemed socket ticket.

    This synthetic request is internal, never accepts a browser-supplied UID.
    POST capability is required even though the WebSocket only delivers state.
    """
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/api/preferans/rooms/realtime-ticket",
            "root_path": "",
            "headers": [(b"authorization", authorization.encode("latin-1"))],
            "query_string": b"",
            "server": ("internal", 443),
        }
    )
    require_preferans_member(request)
    if request.state.portfolio_lab_role not in {"Test", "Admin"}:
        raise HTTPException(403, "Realtime access denied")
    return request.state.preferans_uid, request.state.preferans_owner
