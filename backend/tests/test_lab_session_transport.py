"""Contract tests for separate Firebase ID-token and BFF session transport."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.lab_identity import router
from app.security import firebase_identity


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def _owner_env(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner-uid")


def test_session_cookie_is_independently_verified(monkeypatch) -> None:
    _owner_env(monkeypatch)
    received = []

    def verify_session(cookie):
        received.append(cookie)
        return {"uid": "owner-uid"}

    monkeypatch.setattr(firebase_identity, "verify_session_cookie", verify_session)
    with make_client() as browser:
        response = browser.get(
            "/api/lab/identity", headers={"Authorization": "FirebaseSession signed-cookie"}
        )
    assert response.status_code == 200
    assert response.json() == {"uid": "owner-uid"}
    assert received == ["signed-cookie"]


def test_session_cookie_does_not_grant_another_user_owner_access(monkeypatch) -> None:
    _owner_env(monkeypatch)
    monkeypatch.setattr(firebase_identity, "verify_session_cookie", lambda _: {"uid": "other-uid"})
    with make_client() as browser:
        response = browser.get(
            "/api/lab/identity", headers={"Authorization": "FirebaseSession signed-cookie"}
        )
    assert response.status_code == 403


def test_invalid_session_cookie_fails_closed_without_leaking_errors(monkeypatch) -> None:
    _owner_env(monkeypatch)

    def fail(_):
        raise RuntimeError("confidential Firebase error")

    monkeypatch.setattr(firebase_identity, "verify_session_cookie", fail)
    with make_client() as browser:
        response = browser.get(
            "/api/lab/identity", headers={"Authorization": "FirebaseSession fake-cookie"}
        )
    assert response.status_code == 401
    assert "confidential" not in response.text


def test_invalid_id_token_must_not_fallback_to_session_verifier(monkeypatch) -> None:
    _owner_env(monkeypatch)

    def fail_id(_):
        raise ValueError("invalid ID token")

    def forbidden_session(_):
        raise AssertionError("Session verifier must not be called for ID tokens")

    monkeypatch.setattr(firebase_identity, "verify_id_token", fail_id)
    monkeypatch.setattr(firebase_identity, "verify_session_cookie", forbidden_session)
    with make_client() as browser:
        response = browser.get(
            "/api/lab/identity", headers={"Authorization": "Bearer bad-id-token"}
        )
    assert response.status_code == 401


def test_invalid_session_must_not_fallback_to_id_verifier(monkeypatch) -> None:
    _owner_env(monkeypatch)

    def fail_session(_):
        raise ValueError("invalid session")

    def forbidden_id(_):
        raise AssertionError("ID verifier must not be called for session cookies")

    monkeypatch.setattr(firebase_identity, "verify_id_token", forbidden_id)
    monkeypatch.setattr(firebase_identity, "verify_session_cookie", fail_session)
    with make_client() as browser:
        response = browser.get(
            "/api/lab/identity", headers={"Authorization": "FirebaseSession bad-cookie"}
        )
    assert response.status_code == 401


def test_unknown_schemes_are_not_accepted(monkeypatch) -> None:
    _owner_env(monkeypatch)
    with make_client() as browser:
        for scheme in ("Basic", "Session", "Cookie"):
            assert (
                browser.get(
                    "/api/lab/identity", headers={"Authorization": f"{scheme} token"}
                ).status_code
                == 401
            )


def test_session_transport_is_off_when_lab_is_disabled(monkeypatch) -> None:
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "false")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner-uid")
    with make_client() as browser:
        assert (
            browser.get(
                "/api/lab/identity", headers={"Authorization": "FirebaseSession fake-cookie"}
            ).status_code
            == 404
        )
