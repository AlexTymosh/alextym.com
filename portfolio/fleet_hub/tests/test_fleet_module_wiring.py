"""Contracts for FastAPI host composition and local SQLite continuity."""

from pathlib import Path

from app.main import app
from app.api import vor as legacy_vor
from app.services import vor_store as legacy_store
from fleet_hub.api import vor as owned_vor
from fleet_hub.router import router as fleet_router
from fleet_hub.services import vor_store as owned_store


def test_fleet_host_exposes_same_http_contract_as_public_project_router():
    # FastAPI >=0.137 preserves included routers, so app.routes is no longer
    # a flat APIRoute collection. Use the supported final OpenAPI paths.
    from fastapi import FastAPI

    expected_app = FastAPI()
    expected_app.include_router(fleet_router, prefix="/api")

    def fleet_methods(application):
        return sorted(
            (path, method.upper())
            for path, operations in application.openapi()["paths"].items()
            if path.startswith("/api/vor")
            for method in operations
            if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}
        )

    actual = fleet_methods(app)
    expected = fleet_methods(expected_app)
    assert actual, "Fleet API missing from host OpenAPI"
    assert actual == expected


def test_legacy_imports_alias_real_project_modules():
    assert legacy_vor is owned_vor
    assert legacy_store is owned_store


def test_default_runtime_db_location_does_not_follow_moved_seed(tmp_path, monkeypatch):
    monkeypatch.delenv("VOR_DEMO_DB_PATH", raising=False)
    repo = Path(__file__).resolve().parents[3]
    expected = repo / "backend/_local/vor_hub.sqlite3"
    assert owned_store.SEED_FILE.parent == Path(owned_store.__file__).resolve().parent
    assert owned_store.database_path() == expected
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(tmp_path / "custom.sqlite3"))
    assert owned_store.database_path() == tmp_path / "custom.sqlite3"
