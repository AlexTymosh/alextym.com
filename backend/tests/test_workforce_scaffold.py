"""Structural host boundary tests; independent of optional native Qdrant imports."""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.security.project_grants import require_workforce_member
from workforce_intelligence.router import router


def test_closed_by_default(monkeypatch) -> None:
    monkeypatch.delenv("WORKFORCE_INTELLIGENCE_ENABLED", raising=False)
    app = FastAPI()
    app.include_router(router, prefix="/api", dependencies=[Depends(require_workforce_member)])
    with TestClient(app) as client:
        assert client.get("/api/workforce/status").status_code == 404
        response = client.get("/api/workforce/status", headers={"Authorization": "Bearer bad"})
        assert response.status_code == 404
        assert client.get("/api/workforce/employees").status_code == 404
        assert client.get("/api/workforce/operations/audit").status_code == 404
        assert client.post("/api/workforce/operations", json={}).status_code == 404
        assert client.get("/api/workforce/import/template").status_code == 404
        assert (
            client.post("/api/workforce/import/validate", content=b"not a workbook").status_code
            == 404
        )
        assert client.get("/api/vor/fleet").status_code == 404


def test_host_wiring_applies_shared_auth_to_entire_workforce_router() -> None:
    host_path = Path(__file__).resolve().parents[1] / "app" / "main.py"
    source = ast.parse(host_path.read_text(encoding="utf-8"), filename=str(host_path))
    imports = [
        node
        for node in source.body
        if isinstance(node, ast.ImportFrom) and node.module == "workforce_intelligence.router"
    ]
    assert len(imports) == 1
    assert [(alias.name, alias.asname) for alias in imports[0].names] == [
        ("router", "workforce_router")
    ]
    functions = [
        node
        for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_app"
    ]
    assert len(functions) == 1
    mounts = [
        node
        for node in ast.walk(functions[0])
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "include_router"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "workforce_router"
    ]
    assert len(mounts) == 1
    keywords = {keyword.arg: keyword.value for keyword in mounts[0].keywords}
    assert isinstance(keywords["prefix"], ast.Constant)
    assert keywords["prefix"].value == "/api"
    depend = keywords["dependencies"]
    assert isinstance(depend, ast.List) and len(depend.elts) == 1
    node = depend.elts[0]
    assert isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    assert node.func.id == "Depends"
    assert len(node.args) == 1 and isinstance(node.args[0], ast.Name)
    assert node.args[0].id == "require_workforce_member"
    assert {route.path for route in router.routes} == {
        "/workforce/status",
        "/workforce/demo/status",
        "/workforce/demo/reset",
        "/workforce/demo/seed",
        "/workforce/employees",
        "/workforce/employees/{employee_id}",
        "/workforce/employees/{employee_id}/contracts",
        "/workforce/operations",
        "/workforce/operations/establishment",
        "/workforce/operations/{section}",
        "/workforce/import/template",
        "/workforce/import/validate",
        "/workforce/import/commit",
        "/workforce/import/{batch_id}/errors",
        "/workforce/export",
        "/workforce/vacancies",
        "/workforce/vacancies/{vacancy_id}/cancel",
        "/workforce/starters",
        "/workforce/analytics/executive",
        "/workforce/analytics/candidate-funnel",
        "/workforce/analytics/vacancy-lifecycle",
        "/workforce/metrics",
        "/workforce/data-quality",
        "/workforce/surveys/reports/rota-pressure",
        "/workforce/insight-pilot/query",
    }
