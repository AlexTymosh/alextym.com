"""Password-demo access gates replace Firebase grants for Workforce only."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.security import workforce_demo
from workforce_intelligence.database import Database
from workforce_intelligence.http import get_database
from workforce_intelligence.router import router


def _app():
    app = FastAPI()
    app.include_router(workforce_demo.router, prefix="/api")
    app.include_router(
        router, prefix="/api", dependencies=[Depends(workforce_demo.require_workforce_member)]
    )
    return app


def _password(monkeypatch):
    monkeypatch.setenv("WORKFORCE_INTELLIGENCE_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "synthetic-test-password-only")
    workforce_demo._attempts.clear()


def _session(client: TestClient, password: str = "synthetic-test-password-only") -> str:
    result = client.post("/api/workforce-access/login", json={"password": password})
    assert result.status_code == 200, result.text
    return result.json()["session"]


def test_disabled_without_firebase(monkeypatch):
    monkeypatch.delenv("WORKFORCE_INTELLIGENCE_ENABLED", raising=False)
    with TestClient(_app()) as client:
        assert client.get("/api/workforce/status").status_code == 404
        assert (
            client.post("/api/workforce-access/login", json={"password": "test"}).status_code == 404
        )
        assert client.get("/api/workforce-access/session").status_code == 404


def test_login_fails_closed_when_password_missing(monkeypatch):
    monkeypatch.setenv("WORKFORCE_INTELLIGENCE_ENABLED", "true")
    monkeypatch.delenv("VOR_DEMO_PASSWORD", raising=False)
    with TestClient(_app()) as client:
        assert (
            client.post("/api/workforce-access/login", json={"password": "test"}).status_code == 503
        )
        assert client.get("/api/workforce/status").status_code == 401


def test_password_is_shared_but_fleet_session_is_not(monkeypatch):
    _password(monkeypatch)
    with TestClient(_app()) as client:
        assert (
            client.post("/api/workforce-access/login", json={"password": "wrong"}).status_code
            == 401
        )
        assert client.get("/api/workforce/status").status_code == 401
        assert (
            client.get(
                "/api/workforce/status", headers={"Authorization": "FirebaseSession forged"}
            ).status_code
            == 401
        )
        assert (
            client.get(
                "/api/workforce/status", headers={"Authorization": "Bearer forged"}
            ).status_code
            == 401
        )
        token = _session(client)
        auth = {"Authorization": f"WorkforceDemo {token}"}
        assert client.get("/api/workforce-access/session", headers=auth).json() == {
            "authenticated": True
        }
        response = client.get("/api/workforce/status", headers=auth)
        assert response.status_code == 200
        assert response.json() == {"service": "workforce", "available": True}
        assert response.headers["cache-control"] == "no-store"
        assert (
            client.get(
                "/api/workforce/status", headers={"Cookie": f"vor_demo_session={token}"}
            ).status_code
            == 401
        )


def test_token_expiry_password_rotation_and_forgery(monkeypatch):
    _password(monkeypatch)
    with TestClient(_app()) as client:
        token = _session(client)
        assert workforce_demo.valid_session(f"WorkforceDemo {token}")
        timestamp = int(token.split(".")[1])
        monkeypatch.setattr(workforce_demo, "_now", lambda: timestamp + workforce_demo.SESSION_TTL)
        assert not workforce_demo.valid_session(f"WorkforceDemo {token}")
        monkeypatch.setattr(workforce_demo, "_now", lambda: timestamp)
        changed = token[:-1] + ("0" if token[-1] != "0" else "1")
        assert not workforce_demo.valid_session(f"WorkforceDemo {changed}")
        monkeypatch.setenv("VOR_DEMO_PASSWORD", "rotated-password")
        assert not workforce_demo.valid_session(f"WorkforceDemo {token}")


def test_rate_limit(monkeypatch):
    _password(monkeypatch)
    with TestClient(_app()) as client:
        for _ in range(8):
            assert (
                client.post("/api/workforce-access/login", json={"password": "wrong"}).status_code
                == 401
            )
        assert (
            client.post(
                "/api/workforce-access/login", json={"password": "synthetic-test-password-only"}
            ).status_code
            == 429
        )


def test_rejects_direct_data_before_opening_storage(monkeypatch, tmp_path):
    _password(monkeypatch)
    app = _app()
    database = Database(tmp_path / "workforce.sqlite3")
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(app) as client:
        assert client.get("/api/workforce/analytics/executive").status_code == 401
        assert client.post("/api/workforce/demo/reset", json={}).status_code == 401
        assert not database.path.exists()
        token = _session(client)
        response = client.get(
            "/api/workforce/analytics/executive",
            headers={"Authorization": f"WorkforceDemo {token}"},
        )
        assert response.status_code == 200, response.text
        assert database.path.exists()
        assert response.headers["cache-control"] == "no-store"


def test_other_routes_do_not_require_workforce_password(monkeypatch):
    _password(monkeypatch)
    from app.main import create_app

    with TestClient(create_app()) as client:
        assert client.get("/api/health/live").json() == {"status": "alive"}
        assert client.get("/api/workforce/status").status_code == 401
