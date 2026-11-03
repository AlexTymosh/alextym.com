"""Host/Fleet integration contracts for optional SQLite preparation at startup.

Every Fleet database created by these tests lives under pytest tmp_path.
TestClient is used as a context manager to run the ASGI lifespan.
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from app import main as host


def test_disabled_fleet_does_not_create_database_or_lock(monkeypatch, tmp_path) -> None:
    path = tmp_path / "disabled.sqlite3"
    monkeypatch.setenv("VOR_DEMO_ENABLED", "false")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))

    with TestClient(host.create_app()) as client:
        assert client.app.state.fleet_bootstrap_status == "disabled"
        response = client.get("/api/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    assert not path.exists()
    assert not path.with_name(f".{path.name}.bootstrap.lock").exists()


def test_enabled_fleet_is_initialized_before_first_http_request(monkeypatch, tmp_path) -> None:
    path = tmp_path / "ready.sqlite3"
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")

    with TestClient(host.create_app()) as client:
        # The first HTTP request has not occurred yet.
        assert client.app.state.fleet_bootstrap_status == "ready"
        assert path.is_file()
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0] == 20
            assert db.execute("SELECT COUNT(*) FROM ops_stage_settings").fetchone()[0] == 18
            assert db.execute("SELECT COUNT(*) FROM vor_status_events").fetchone()[0] >= 20
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []

        response = client.get("/api/health/live")
        assert response.status_code == 200


def test_restart_repairs_missing_ops_schema_without_overwriting_manual_edits(
    monkeypatch, tmp_path
) -> None:
    path = tmp_path / "recover.sqlite3"
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))

    with TestClient(host.create_app()) as client:
        assert client.app.state.fleet_bootstrap_status == "ready"

    with sqlite3.connect(path) as db:
        db.execute("UPDATE vehicles SET garage='Owner workshop' WHERE id=1")
        db.execute(
            "UPDATE ops_stage_settings SET label='Custom label' "
            "WHERE stage_index=0 AND item_key='response_received'"
        )
        db.execute("DROP TABLE ops_audit")
        db.commit()

    with TestClient(host.create_app()) as client:
        assert client.app.state.fleet_bootstrap_status == "ready"
        with sqlite3.connect(path) as db:
            garage = db.execute("SELECT garage FROM vehicles WHERE id=1").fetchone()[0]
            assert garage == "Owner workshop"
            custom = db.execute(
                "SELECT label FROM ops_stage_settings "
                "WHERE stage_index=0 AND item_key='response_received'"
            ).fetchone()[0]
            assert custom == "Custom label"
            assert db.execute("SELECT 1 FROM sqlite_master WHERE name='ops_audit'").fetchone()
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_optional_fleet_startup_failure_does_not_disable_main_site(monkeypatch) -> None:
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")

    def broken_bootstrap() -> bool:
        raise RuntimeError("synthetic Fleet startup failure")

    monkeypatch.setattr(host, "prepare_demo_database", broken_bootstrap)
    with TestClient(host.create_app()) as client:
        assert client.app.state.fleet_bootstrap_status == "failed"
        response = client.get("/api/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}
