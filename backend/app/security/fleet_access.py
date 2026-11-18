"""Host adapter for Firebase authorization of every Fleet route."""

import os

from fastapi import HTTPException, Request
from fleet_hub.router import require_demo_access

from app.security.project_grants import require_project_access


def require_fleet_access(request: Request) -> None:
    if os.getenv("PORTFOLIO_LAB_ENABLED") != "true":
        require_demo_access(request)
        return
    if os.getenv("VOR_DEMO_ENABLED", "false").lower() != "true":
        raise HTTPException(404, "Demo disabled")
    require_project_access(request, "fleet_hub")


def guard_fleet_routes(request: Request) -> None:
    if os.getenv("PORTFOLIO_LAB_ENABLED") == "true":
        if request.url.path == "/api/vor/login":
            raise HTTPException(404, "Not found")
        require_fleet_access(request)
