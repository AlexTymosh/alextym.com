"""Shared project grants enforce access on the direct backend origin."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.security import firebase_identity
from app.security.project_grants import (
    project_grant_role,
    project_role_allows,
    require_project_access,
)

NOW = 1_800_000_000_000
GRANT = {
    "schema_version": 1,
    "uid": "user",
    "project_id": "fleet_hub",
    "role": "View",
    "status": "active",
}


def test_project_grant_identity_expiry_and_revocation():
    assert project_grant_role("user", "fleet_hub", GRANT, NOW) == "View"
    assert project_grant_role("other", "fleet_hub", GRANT, NOW) is None
    assert project_grant_role("user", "workforce_intelligence", GRANT, NOW) is None
    assert project_grant_role("user", "fleet_hub", {**GRANT, "status": "revoked"}, NOW) is None
    assert project_grant_role("user", "fleet_hub", {**GRANT, "expires_at_ms": NOW}, NOW) is None
    assert (
        project_grant_role("user", "fleet_hub", {**GRANT, "expires_at_ms": NOW + 1}, NOW) == "View"
    )
    assert project_grant_role("user", "fleet_hub", {**GRANT, "role": "Owner"}, NOW) is None


@pytest.mark.parametrize(
    "role,read,write,reset",
    [("View", True, False, False), ("Test", True, True, False), ("Admin", True, True, True)],
)
def test_capability_policy(role, read, write, reset):
    assert project_role_allows(role, "GET", "/api/vor/bootstrap") is read
    assert project_role_allows(role, "POST", "/api/vor/bookings") is write
    assert project_role_allows(role, "POST", "/api/workforce/demo/reset") is reset
    assert project_role_allows(role, "POST", "/api/vor/workflows/create") is reset
    assert not project_role_allows(None, "GET", "/api/vor/bootstrap")


def test_direct_api_rechecks_grants_and_never_uses_email(monkeypatch):
    from app.security import project_grants

    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    monkeypatch.setattr(firebase_identity, "require_lab_identity", lambda request: {"uid": "user"})
    record = dict(GRANT)
    monkeypatch.setattr(project_grants, "load_project_grant", lambda project_id, uid: record)
    app = FastAPI()

    @app.get("/api/vor/bootstrap")
    def fleet(request: Request):
        return require_project_access(request, "fleet_hub")

    @app.get("/api/workforce/status")
    def workforce(request: Request):
        return require_project_access(request, "workforce_intelligence")

    with TestClient(app) as client:
        assert client.get("/api/vor/bootstrap").status_code == 200
        assert client.get("/api/workforce/status").status_code == 403
        record["status"] = "revoked"
        assert client.get("/api/vor/bootstrap").status_code == 403
        record.clear()
        assert client.get("/api/vor/bootstrap").status_code == 403


def test_lab_mode_rejects_legacy_fleet_password_and_missing_credentials(monkeypatch):
    from app.main import create_app

    monkeypatch.setattr("app.main.prepare_demo_database", lambda: False)
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("WORKFORCE_INTELLIGENCE_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "synthetic-legacy-password")
    with TestClient(create_app()) as client:
        assert (
            client.post(
                "/api/vor/login", json={"password": "synthetic-legacy-password"}
            ).status_code
            == 404
        )
        assert client.get("/api/vor/bootstrap").status_code == 401
        assert client.get("/api/workforce/status").status_code == 401
        assert (
            client.post(
                "/api/workforce-access/login", json={"password": "synthetic-legacy-password"}
            ).status_code
            == 404
        )
