"""Storage failures stay generic over HTTP and useful without logging secrets."""

import json

import firebase_admin
import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from firebase_admin import firestore
from google.api_core.exceptions import PermissionDenied

from preferans.online import router as api
from preferans.online.store import FirestoreRooms, StoreError


@pytest.fixture
def client(monkeypatch):
    def verified_context(request: Request):
        request.state.preferans_uid = "synthetic-admin"
        request.state.preferans_owner = True
        request.state.request_id = "req_storage_diagnostic_test"

    monkeypatch.setattr(firebase_admin, "get_app", lambda _: object())
    monkeypatch.setattr(firestore, "client", lambda **_: object())
    app = FastAPI()
    app.include_router(api.router, dependencies=[Depends(verified_context)])
    with TestClient(app) as http:
        yield http


@pytest.mark.parametrize(
    "method,path,operation,body",
    [
        (
            "POST",
            "/preferans/rooms",
            "create",
            {"idempotency_key": "private-token-0001"},
        ),
        ("GET", "/preferans/history", "history", None),
        ("GET", "/preferans/rankings", "rankings", None),
    ],
)
def test_sdk_failure_logs_only_operation_type_stage_and_request_id(
    client, monkeypatch, caplog, method, path, operation, body
):
    def denied(*_args, **_kwargs):
        raise PermissionDenied("private-key TOKEN closed-hand secret-provider-metadata")

    monkeypatch.setattr(FirestoreRooms, operation, denied)
    response = client.request(method, path, json=body)
    assert response.status_code == 503
    assert response.json() == {"detail": "Storage unavailable"}
    records = [record for record in caplog.records if record.name == api.__name__]
    assert len(records) == 1
    assert records[0].exc_info is None
    assert json.loads(records[0].getMessage()) == {
        "event": "preferans.storage.failed",
        "operation": operation,
        "stage": "operation",
        "error_type": "PermissionDenied",
        "request_id": "req_storage_diagnostic_test",
    }
    for secret in (
        "private-key",
        "TOKEN",
        "closed-hand",
        "secret-provider-metadata",
        "private-token",
    ):
        assert secret not in caplog.text + response.text


def test_initialization_failure_is_distinguished_from_an_operation(client, monkeypatch, caplog):
    def unavailable(**_kwargs):
        raise ValueError("private credential data")

    monkeypatch.setattr(firestore, "client", unavailable)
    assert client.get("/preferans/history").status_code == 503
    diagnostic = json.loads(caplog.records[-1].getMessage())
    assert diagnostic["stage"] == "initialization"
    assert diagnostic["operation"] == "history"
    assert diagnostic["error_type"] == "ValueError"
    assert "private credential data" not in caplog.text


@pytest.mark.parametrize("code", [409, 503])
def test_domain_failures_keep_their_status(client, monkeypatch, caplog, code):
    def unavailable(*_args, **_kwargs):
        raise StoreError(code, "Game state unavailable")

    monkeypatch.setattr(FirestoreRooms, "history", unavailable)
    assert client.get("/preferans/history").status_code == code
    records = [record for record in caplog.records if record.name == api.__name__]
    assert len(records) == (1 if code == 503 else 0)
    if records:
        assert json.loads(records[0].getMessage())["stage"] == "state"
