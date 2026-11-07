"""Two existing Fleet advance routes use the same service without router imports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fleet_hub.api.vor import router as vor_router
from fleet_hub.api.vor_checklist import CHECKLIST, router as checklist_router
from fleet_hub.services import vor_checklist_advance as workflow

ADVANCE_ROUTES = ("/api/vor/advance", "/api/vor/checklists/advance")
BODY = {"vehicle_id": 1, "ticket_id": "PS000100"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "fixture-secret")
    app = FastAPI()
    app.include_router(vor_router, prefix="/api")
    app.include_router(checklist_router, prefix="/api")
    with TestClient(app) as c:
        yield c


def test_checklist_constant_is_shared() -> None:
    assert CHECKLIST is workflow.CHECKLIST


@pytest.mark.parametrize("path", ADVANCE_ROUTES)
def test_both_routes_delegate_to_the_same_service(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    calls: list[tuple[int, str]] = []

    def fake_advance(vehicle_id: int, ticket_id: str) -> dict[str, bool]:
        calls.append((vehicle_id, ticket_id))
        return {"ok": True}

    monkeypatch.setattr(workflow, "advance_with_checks", fake_advance)
    assert client.post("/api/vor/login", json={"password": "fixture-secret"}).status_code == 200
    response = client.post(path, json=BODY)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert calls == [(1, "PS000100")]


@pytest.mark.parametrize("path", ADVANCE_ROUTES)
@pytest.mark.parametrize(
    "code,detail",
    [
        (404, "Ticket not found for vehicle"),
        (409, "Complete the current stage checklist before advancing"),
    ],
)
def test_both_routes_preserve_service_error_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    code: int,
    detail: str,
) -> None:
    def rejected(vehicle_id: int, ticket_id: str) -> dict[str, bool]:
        raise workflow.ChecklistAdvanceError(code, detail)

    monkeypatch.setattr(workflow, "advance_with_checks", rejected)
    assert client.post("/api/vor/login", json={"password": "fixture-secret"}).status_code == 200
    response = client.post(path, json=BODY)
    assert response.status_code == code
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("path", ADVANCE_ROUTES)
def test_both_routes_require_authentication_and_same_origin(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setattr(workflow, "advance_with_checks", lambda *_: {"ok": True})
    unauth = client.post(path, json=BODY)
    assert unauth.status_code == 401
    assert unauth.json()["detail"] == "Password required"
    assert client.post("/api/vor/login", json={"password": "fixture-secret"}).status_code == 200
    origin = client.post(path, json=BODY, headers={"Origin": "https://untrusted.invalid"})
    assert origin.status_code == 403
    assert origin.json()["detail"] == "Invalid origin"


def test_shared_workflow_and_routers_have_no_wrong_direction_imports() -> None:
    for module in ("fleet_hub.api.vor", "fleet_hub.api.vor_checklist"):
        path = Path(__import__(module, fromlist=["__file__"]).__file__)
        parsed = ast.parse(path.read_text(encoding="utf-8"))
        imports = [n.module or "" for n in ast.walk(parsed) if isinstance(n, ast.ImportFrom)]
        assert not any(name.startswith("fleet_hub.api.vor_") for name in imports)
    path = Path(workflow.__file__)
    parsed = ast.parse(path.read_text(encoding="utf-8"))
    imports = [n.module or "" for n in ast.walk(parsed) if isinstance(n, ast.ImportFrom)]
    assert not any(name.startswith("fleet_hub.api") for name in imports)
