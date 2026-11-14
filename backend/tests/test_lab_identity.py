"""No-provider negative security tests for the protected direct-origin identity probe."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security import firebase_identity
from app.api.lab_identity import router


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_disabled_probe_is_not_public(monkeypatch) -> None:
    monkeypatch.delenv("PORTFOLIO_LAB_ENABLED", raising=False)
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner-uid")
    with client() as browser:
        assert browser.get("/api/lab/identity").status_code == 404


def test_enabled_probe_requires_configured_owner(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.delenv("PORTFOLIO_LAB_OWNER_UID", raising=False)
    with client() as browser:
        assert browser.get("/api/lab/identity").status_code == 503


def test_missing_and_malformed_bearer_tokens_are_denied(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner-uid")
    with client() as browser:
        assert browser.get("/api/lab/identity").status_code == 401
        for value in ["Basic abc", "Bearer ", "Bearer " + "x" * 9000]:
            assert (
                browser.get("/api/lab/identity", headers={"Authorization": value}).status_code
                == 401
            )


def test_verified_other_user_cannot_assume_owner(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner-uid")
    monkeypatch.setattr(firebase_identity, "verify_id_token", lambda token: {"uid": "other-uid"})
    monkeypatch.setattr(firebase_identity, "load_lab_identity", lambda uid: None)
    with client() as browser:
        assert (
            browser.get(
                "/api/lab/identity", headers={"Authorization": "Bearer valid-synthetic"}
            ).status_code
            == 403
        )


def test_only_verified_pinned_owner_is_admitted(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner-uid")
    monkeypatch.setattr(
        firebase_identity,
        "verify_id_token",
        lambda token: {"uid": "owner-uid", "firebase": {"sign_in_provider": "password"}},
    )
    with client() as browser:
        response = browser.get(
            "/api/lab/identity", headers={"Authorization": "Bearer valid-synthetic"}
        )
    assert response.status_code == 200
    assert response.json() == {"uid": "owner-uid"}


def test_provider_verification_failure_is_not_exposed(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner-uid")

    def fail(token: str) -> dict:
        raise RuntimeError("sensitive SDK error")

    monkeypatch.setattr(firebase_identity, "verify_id_token", fail)
    with client() as browser:
        response = browser.get("/api/lab/identity", headers={"Authorization": "Bearer synthetic"})
    assert response.status_code == 401
    assert "sensitive" not in response.text
