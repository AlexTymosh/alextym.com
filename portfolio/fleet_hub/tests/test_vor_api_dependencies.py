"""Fleet shared auth/origin dependency contracts; no SQLite files needed."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fleet_hub.api import dependencies as auth
from fleet_hub.api import vor
from fleet_hub.router import router as fleet_router


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "fixture-password")
    monkeypatch.delenv("VOR_DEMO_ALLOWED_ORIGINS", raising=False)
    app = FastAPI()
    app.include_router(fleet_router, prefix="/api")
    with TestClient(app) as test_client:
        yield test_client


def test_legacy_vor_helpers_reexport_same_dependency_functions() -> None:
    for name in (
        "COOKIE",
        "SESSION_TTL",
        "enabled",
        "secret",
        "sign",
        "session_valid",
        "required",
        "same_origin",
    ):
        assert getattr(vor, name) is getattr(auth, name)


@pytest.mark.parametrize(
    "path",
    [
        "/api/vor/bootstrap",
        "/api/vor/checklists/PS000100",
        "/api/vor/data/register",
        "/api/vor/intake/options",
        "/api/vor/ops/overview",
        "/api/vor/reconciliation/batches",
        "/api/vor/reporting/dashboard",
        "/api/vor/workflow-admin",
    ],
)
def test_all_fleet_routers_share_authentication(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 401, (path, response.text)
    assert response.json()["detail"] == "Password required"


def test_disabled_demo_returns_404_not_401(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOR_DEMO_ENABLED", "false")
    response = client.get("/api/vor/reporting/dashboard")
    assert response.status_code == 404
    assert response.json()["detail"] == "Demo disabled"


def test_session_cookie_contract_survives_extraction(client: TestClient) -> None:
    assert client.get("/api/vor/session").json()["authenticated"] is False
    assert client.post("/api/vor/login", json={"password": "wrong"}).status_code == 401
    response = client.post("/api/vor/login", json={"password": "fixture-password"})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "vor_demo_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/api/vor" in cookie
    assert client.get("/api/vor/session").json()["authenticated"] is True
    assert client.post("/api/vor/logout").status_code == 200
    assert client.get("/api/vor/session").json()["authenticated"] is False


def test_origin_checks_on_login_and_authenticated_mutations(client: TestClient) -> None:
    malicious = {"origin": "https://untrusted.example"}
    login = {"password": "fixture-password"}
    response = client.post("/api/vor/login", json=login, headers=malicious)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid origin"

    # A configured frontend origin is permitted behind a reverse proxy.
    assert (
        client.post(
            "/api/vor/login", json=login, headers={"origin": "http://localhost:3000"}
        ).status_code
        == 200
    )
    mutation = client.post(
        "/api/vor/contacts",
        json={"name": "Test", "email": "test@example.com", "role": "external"},
        headers=malicious,
    )
    assert mutation.status_code == 403
    assert mutation.json()["detail"] == "Invalid origin"


def test_invalid_signature_cannot_authenticate(client: TestClient) -> None:
    client.cookies.set(auth.COOKIE, "1000000000.invalid", path="/api/vor")
    assert client.get("/api/vor/session").json()["authenticated"] is False
