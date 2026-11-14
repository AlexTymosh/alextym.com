"""Backend identity admission mirrors the Next.js acceptance contract."""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.lab_identity import router
from app.security import firebase_identity
from app.security.lab_admission import admission_decision, sign_in_provider


FIXTURES = json.loads(
    (
        Path(__file__).resolve().parents[2] / "docs/contracts/portfolio-lab-admission-cases.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", FIXTURES, ids=lambda case: case["name"])
def test_shared_admission_contract(case) -> None:
    assert (
        admission_decision(
            case["uid"],
            case["owner_uid"],
            case["provider"],
            case["record"],
            case["now_ms"],
            case.get("auth_time"),
            case.get("subject"),
        )
        == case["want"]
    )


def test_provider_extracted_only_from_trusted_verified_claims() -> None:
    assert sign_in_provider({"email": "attacker@example.test"}) == ""
    assert sign_in_provider({"firebase": {"sign_in_provider": "google.com"}}) == "google.com"
    assert sign_in_provider({"firebase": {"sign_in_provider": None}}) == ""


def test_uninvited_valid_token_denied(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    monkeypatch.setattr(
        firebase_identity,
        "verify_id_token",
        lambda token: {"uid": "other", "firebase": {"sign_in_provider": "password"}},
    )
    monkeypatch.setattr(firebase_identity, "load_lab_identity", lambda uid: None)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        assert (
            client.get("/api/lab/identity", headers={"Authorization": "Bearer token"}).status_code
            == 403
        )


def test_firestore_outage_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    monkeypatch.setattr(
        firebase_identity,
        "verify_session_cookie",
        lambda token: {"uid": "other", "firebase": {"sign_in_provider": "password"}},
    )

    def unavailable(_uid):
        raise RuntimeError("secret service failure")

    monkeypatch.setattr(firebase_identity, "load_lab_identity", unavailable)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        response = client.get(
            "/api/lab/identity", headers={"Authorization": "FirebaseSession signed"}
        )
    assert response.status_code == 503
    assert "secret service" not in response.text


def test_expired_password_denied_on_existing_session(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    monkeypatch.setattr(
        firebase_identity,
        "verify_session_cookie",
        lambda token: {"uid": "other", "firebase": {"sign_in_provider": "password"}},
    )
    monkeypatch.setattr(
        firebase_identity,
        "load_lab_identity",
        lambda uid: {
            "schema_version": 1,
            "uid": uid,
            "status": "active",
            "password_state": "initial",
            "initial_password_expires_at_ms": 1,
        },
    )
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        response = client.get(
            "/api/lab/identity", headers={"Authorization": "FirebaseSession signed"}
        )
    assert response.status_code == 403
