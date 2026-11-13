"""Dependency-light security checks for the closed Workforce project foundation.

Keep the module registration contract independent of unrelated native RAG imports:
full FastAPI host integration is exercised by the existing backend suite on CI.
"""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from workforce_intelligence.router import router


def test_all_workforce_requests_fail_closed_even_with_flag_and_header(monkeypatch) -> None:
    monkeypatch.setenv("WORKFORCE_INTELLIGENCE_ENABLED", "true")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        for headers in ({}, {"Authorization": "Bearer arbitrary"}):
            response = client.get("/api/workforce/status", headers=headers)
            assert response.status_code == 404
        assert client.post("/api/workforce/status").status_code in (404, 405)
        assert client.get("/api/workforce/employees").status_code == 404
        assert client.get("/api/vor/fleet").status_code == 404


def test_host_registers_only_the_closed_workforce_probe() -> None:
    """Verify host wiring without importing Chat/RAG/Qdrant native dependencies."""
    host_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    source = ast.parse(host_path.read_text(encoding="utf-8"), filename=str(host_path))

    imports = [
        stmt
        for stmt in source.body
        if isinstance(stmt, ast.ImportFrom) and stmt.module == "workforce_intelligence.router"
    ]
    assert len(imports) == 1
    assert [(alias.name, alias.asname) for alias in imports[0].names] == [
        ("router", "workforce_router")
    ]

    factories = [
        stmt
        for stmt in source.body
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == "create_app"
    ]
    assert len(factories) == 1

    mounts = [
        call
        for call in ast.walk(factories[0])
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "include_router"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "app"
        and len(call.args) == 1
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "workforce_router"
    ]
    assert len(mounts) == 1
    assert len(mounts[0].keywords) == 1
    assert mounts[0].keywords[0].arg == "prefix"
    assert isinstance(mounts[0].keywords[0].value, ast.Constant)
    assert mounts[0].keywords[0].value.value == "/api"
    assert {route.path for route in router.routes} == {"/workforce/status"}
