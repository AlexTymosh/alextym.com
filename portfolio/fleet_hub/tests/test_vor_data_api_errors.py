"""Prevent internal error disclosures from all Fleet VOR v2 data routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fleet_hub.api.vor import required
from fleet_hub.api.vor_data import router
from fleet_hub.services import vor_data

SENSITIVE = "sqlite:///private/fleet.db password=never-expose traceback=secret"

# Exercise every route identified in the six CodeQL review threads.
ROUTES = [
    ("GET", "/api/vor/data/register", "register_list", None),
    (
        "POST",
        "/api/vor/data/vehicles",
        "register_vehicle",
        {"registration": "AB26 XYZ", "model": "Ford Transit", "garage": "Test depot"},
    ),
    (
        "POST",
        "/api/vor/data/vehicles/1/archive",
        "archive_vehicle",
        {"archived": True},
    ),
    (
        "POST",
        "/api/vor/data/vehicles/1/status",
        "update_status",
        {"status": "Operational", "actor": "Fleet Department", "reason": "Manual confirmation"},
    ),
    (
        "POST",
        "/api/vor/data/imports/preview",
        "prepare_import",
        {"filename": "fleet.csv", "content_b64": "QUJD", "mode": "skip"},
    ),
    (
        "POST",
        "/api/vor/data/imports/commit",
        "commit_import",
        {"filename": "fleet.csv", "content_b64": "QUJD", "mode": "skip", "digest": "0" * 64},
    ),
]


@pytest.mark.parametrize("method,path,operation,payload", ROUTES)
@pytest.mark.parametrize(
    "exception_type,expected_status,expected_detail",
    [
        (ValueError, 400, "Invalid fleet data request"),
        (RuntimeError, 503, "Fleet data service unavailable"),
    ],
)
def test_data_api_never_exposes_internal_exceptions(
    monkeypatch,
    method,
    path,
    operation,
    payload,
    exception_type,
    expected_status,
    expected_detail,
):
    def internal_failure(*_args, **_kwargs):
        raise exception_type(SENSITIVE)

    monkeypatch.setattr(vor_data, operation, internal_failure)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[required] = lambda: None

    with TestClient(app) as client:
        if method == "GET":
            response = client.get(path)
        else:
            response = client.post(path, json=payload)

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert SENSITIVE not in response.text
    assert "traceback" not in response.text.lower()


def test_data_api_success_remains_unchanged(monkeypatch):
    expected = {"vehicles": [], "cases": [], "statuses": [], "batches": []}
    monkeypatch.setattr(vor_data, "register_list", lambda include_archived: expected)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[required] = lambda: None

    with TestClient(app) as client:
        response = client.get("/api/vor/data/register")

    assert response.status_code == 200
    assert response.json() == expected
