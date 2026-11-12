"""Legacy Fleet security baselines before the Portfolio Lab authentication migration.

Intentionally test current Fleet auth, not an imaginary Firebase deployment.
PR 5 must replace these assertions alongside the new RBAC negative tests.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRoute
from starlette.requests import Request

from fleet_hub.api.dependencies import required, same_origin
from fleet_hub.api import (
    vor,
    vor_checklist,
    vor_data,
    vor_intake,
    vor_operations,
    vor_reconciliation,
    vor_reporting,
    vor_workflow_admin,
)
from fleet_hub.router import router as fleet_router


PUBLIC_LEGACY = {("GET", "/vor/session"), ("POST", "/vor/login"), ("POST", "/vor/logout")}


def request(origin: str | None = None, host: str = "alextym.com") -> Request:
    headers = [(b"host", host.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    return Request(
        {"type": "http", "method": "GET", "path": "/api/vor/bootstrap", "headers": headers}
    )


def test_current_protected_fleet_routes_require_legacy_session() -> None:
    # FastAPI >= 0.137 retains included routers instead of flattening them.
    # Inspect leaf routers, then compare their endpoints with public OpenAPI.
    modules = (
        vor,
        vor_workflow_admin,
        vor_reporting,
        vor_reconciliation,
        vor_operations,
        vor_checklist,
        vor_data,
        vor_intake,
    )
    routes = [
        route for module in modules for route in module.router.routes if isinstance(route, APIRoute)
    ]
    assert len(routes) >= 20, "Unexpected Fleet API shrinkage"

    probe = FastAPI()
    probe.include_router(fleet_router, prefix="/api")
    published = {
        (path, method.upper())
        for path, operations in probe.openapi()["paths"].items()
        for method in operations
        if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}
    }
    protected_inventory = {
        (f"/api{route.path}", method) for route in routes for method in route.methods
    }
    assert published == protected_inventory, "Fleet route inventory differs from published API"
    seen_public: set[tuple[str, str]] = set()
    for route in routes:
        for method in route.methods:
            item = (method, route.path)
            if item in PUBLIC_LEGACY:
                seen_public.add(item)
            else:
                assert any(
                    dependency.call is required for dependency in route.dependant.dependencies
                ), f"Unprotected Fleet endpoint: {method} {route.path}"
    assert seen_public == PUBLIC_LEGACY


def test_disabled_fleet_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOR_DEMO_ENABLED", "false")
    with pytest.raises(HTTPException) as exc:
        required(request())
    assert exc.value.status_code == 404


def test_enabled_fleet_without_session_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    with pytest.raises(HTTPException) as exc:
        required(request())
    assert exc.value.status_code == 401


def test_untrusted_origin_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOR_DEMO_ALLOWED_ORIGINS", "https://alextym.com")
    with pytest.raises(HTTPException) as exc:
        same_origin(request("https://untrusted.example"))
    assert exc.value.status_code == 403


def test_approved_origin_does_not_grant_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    same_origin(request("https://alextym.com"))
    with pytest.raises(HTTPException) as exc:
        required(request("https://alextym.com"))
    assert exc.value.status_code == 401
