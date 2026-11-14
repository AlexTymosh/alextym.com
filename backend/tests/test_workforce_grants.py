"""Fail-closed Workforce grant behavior without native RAG import dependencies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.security import firebase_identity, project_grants
from workforce_intelligence.router import router

CASES = json.loads(
    (Path(__file__).resolve().parents[2] / "docs/contracts/workforce-grant-cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_python_js_share_exact_grant_policy(case) -> None:
    assert (
        project_grants.admin_grant_allows(
            case["uid"], case["project_id"], case["record"], case["now_ms"]
        )
        is case["want"]
    )


def app_client() -> TestClient:
    app = FastAPI()
    app.include_router(
        router, prefix="/api", dependencies=[Depends(project_grants.require_workforce_member)]
    )
    return TestClient(app)


def setup_verified_user(monkeypatch, uid: str = "user") -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("WORKFORCE_INTELLIGENCE_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    monkeypatch.setattr(
        firebase_identity,
        "verify_id_token",
        lambda _token: {"uid": uid, "firebase": {"sign_in_provider": "password"}},
    )
    monkeypatch.setattr(
        firebase_identity,
        "load_lab_identity",
        lambda _uid: {
            "schema_version": 1,
            "uid": uid,
            "status": "active",
            "password_state": "user_set",
        },
    )


def granted(uid: str = "user") -> dict:
    return {
        "schema_version": 1,
        "uid": uid,
        "project_id": project_grants.WORKFORCE_PROJECT_ID,
        "status": "active",
        "role": "Admin",
    }


def test_feature_disabled_returns_404_without_calling_auth(monkeypatch) -> None:
    monkeypatch.delenv("WORKFORCE_INTELLIGENCE_ENABLED", raising=False)
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    with app_client() as client:
        assert client.get("/api/workforce/status").status_code == 404


def test_no_identity_and_invalid_bearer_never_open_project(monkeypatch) -> None:
    setup_verified_user(monkeypatch)
    monkeypatch.setattr(project_grants, "load_project_grant", lambda *_: granted())
    with app_client() as client:
        assert client.get("/api/workforce/status").status_code == 401
        response = client.get("/api/workforce/status", headers={"Authorization": "Basic invalid"})
        assert response.status_code == 401


def test_valid_identity_without_project_grant_cannot_enter(monkeypatch) -> None:
    setup_verified_user(monkeypatch)
    monkeypatch.setattr(project_grants, "load_project_grant", lambda *_: None)
    with app_client() as client:
        response = client.get(
            "/api/workforce/status", headers={"Authorization": "Bearer synthetic"}
        )
    assert response.status_code == 403


def test_project_member_can_use_status_but_only_while_grant_active(monkeypatch) -> None:
    setup_verified_user(monkeypatch)
    store = {"record": granted()}
    monkeypatch.setattr(project_grants, "load_project_grant", lambda *_: store["record"])
    with app_client() as client:
        headers = {"Authorization": "Bearer synthetic"}
        good = client.get("/api/workforce/status", headers=headers)
        assert good.status_code == 200
        assert good.json() == {"service": "workforce", "available": True}
        assert good.headers["cache-control"] == "no-store"
        store["record"]["status"] = "revoked"
        assert client.get("/api/workforce/status", headers=headers).status_code == 403


def test_owner_can_enter_without_explicit_grant(monkeypatch) -> None:
    setup_verified_user(monkeypatch, uid="owner")

    def forbidden_lookup(*_args) -> None:
        raise AssertionError("Owner should not need a project grant")

    monkeypatch.setattr(project_grants, "load_project_grant", forbidden_lookup)
    with app_client() as client:
        response = client.get("/api/workforce/status", headers={"Authorization": "Bearer owner"})
    assert response.status_code == 200


def test_firestore_failure_denies_open_project(monkeypatch) -> None:
    setup_verified_user(monkeypatch)

    def fail(*_args) -> None:
        raise OSError("do not leak an internal credential")

    monkeypatch.setattr(project_grants, "load_project_grant", fail)
    with app_client() as client:
        response = client.get(
            "/api/workforce/status", headers={"Authorization": "Bearer synthetic"}
        )
    assert response.status_code == 503
    assert "credential" not in response.text


def test_other_projects_cannot_be_queried_by_workforce_path(monkeypatch) -> None:
    setup_verified_user(monkeypatch)
    calls = []

    def grant_lookup(project: str, uid: str) -> dict:
        calls.append((project, uid))
        return {**granted(), "project_id": "fleet_hub"}

    monkeypatch.setattr(project_grants, "load_project_grant", grant_lookup)
    with app_client() as client:
        response = client.get(
            "/api/workforce/status", headers={"Authorization": "Bearer synthetic"}
        )
        assert response.status_code == 403
    assert calls == [("workforce_intelligence", "user")]


def test_missing_application_route_stays_missing(monkeypatch) -> None:
    setup_verified_user(monkeypatch)
    monkeypatch.setattr(project_grants, "load_project_grant", lambda *_: granted())
    with app_client() as client:
        response = client.get(
            "/api/workforce/employees", headers={"Authorization": "Bearer synthetic"}
        )
        assert response.status_code == 404
