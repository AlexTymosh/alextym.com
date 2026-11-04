"""Durable Fleet live-mail retry protection; all SQLite files use pytest tmp_path."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fleet_hub.api.vor import router
from fleet_hub.services import message_delivery as delivery
from fleet_hub.services import vor_store


KEY = "123e4567-e89b-42d3-a456-426614174000"


@pytest.fixture
def setup(monkeypatch, tmp_path):
    path = tmp_path / "idempotent.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(path))
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "fixture-password")
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "true")
    monkeypatch.setenv("VOR_DEMO_ALLOWED_EMAIL_DOMAINS", "*")
    monkeypatch.setenv("VOR_DEMO_ALLOWED_RECIPIENTS", "")
    monkeypatch.setenv("VOR_DEMO_EMAIL_LIMIT", "30")
    monkeypatch.setenv("RESEND_API_KEY", "fake-token")
    monkeypatch.setenv("VOR_DEMO_FROM_EMAIL", "demo@verified.example")
    monkeypatch.setenv("VOR_DEMO_PUBLIC_URL", "https://fleet.example/hub")
    with vor_store.connection() as db:
        vehicle_id = db.execute("SELECT id FROM vehicles ORDER BY id LIMIT 1").fetchone()[0]
    return path, vehicle_id


def send(vehicle_id, *, request_id=KEY, text="one notification"):
    return delivery.post_message(
        vehicle_id=vehicle_id,
        ticket_id=None,
        kind="email",
        text=text,
        subject="Workshop update",
        request_id=request_id,
    )


def _attempt_status(db: sqlite3.Connection, request_id: str) -> str:
    # Return only the attempt belonging to the given request.
    row = db.execute(
        "SELECT a.status FROM vor_email_delivery_attempts AS a "
        "JOIN vor_email_requests AS r ON r.reservation_id = a.id "
        "WHERE r.request_id = ?",
        (request_id,),
    ).fetchone()
    assert row is not None
    return str(row[0])


def fake_provider(monkeypatch):
    calls = []

    class Accepted:
        def raise_for_status(self):
            pass

    def post(_url, **kwargs):
        calls.append(kwargs)
        return Accepted()

    monkeypatch.setattr(delivery.httpx, "post", post)
    return calls


def test_replay_after_accepted_mail_does_not_send_or_insert_second_event(setup, monkeypatch):
    path, vid = setup
    calls = fake_provider(monkeypatch)
    before = vor_store.snapshot()["events"]
    with sqlite3.connect(path) as db:
        attempts_before = db.execute("SELECT count(*) FROM vor_email_delivery_attempts").fetchone()[
            0
        ]
    first = send(vid)
    assert first["delivery"] == "outgoing"
    second = send(vid)
    assert second == first
    assert len(calls) == 1
    assert calls[0]["headers"]["Idempotency-Key"] == "fleet-message/" + KEY
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT count(*) FROM vor_email_delivery_attempts").fetchone()[0]
            == attempts_before + 1
        )
        assert _attempt_status(db, KEY) == "accepted"
        assert db.execute("SELECT count(*) FROM vor_email_requests").fetchone()[0] == 1
    assert len(vor_store.snapshot()["events"]) == len(before) + 1


def test_changed_payload_same_key_is_rejected_without_second_send(setup, monkeypatch):
    _, vid = setup
    calls = fake_provider(monkeypatch)
    send(vid)
    with pytest.raises(delivery.MessageDeliveryError) as exc:
        send(vid, text="different notification")
    assert exc.value.reason == "request_id_conflict"
    assert len(calls) == 1


def test_provider_timeout_is_uncertain_and_never_automatically_resent(setup, monkeypatch):
    path, vid = setup
    calls = []

    def timeout(*args, **kwargs):
        calls.append(kwargs)
        raise httpx.ReadTimeout("provider uncertain")

    monkeypatch.setattr(delivery.httpx, "post", timeout)
    with pytest.raises(delivery.MessageDeliveryError) as first:
        send(vid)
    assert first.value.reason == "provider_unavailable"
    with pytest.raises(delivery.MessageDeliveryError) as second:
        send(vid)
    assert second.value.reason == "delivery_uncertain"
    assert len(calls) == 1
    with sqlite3.connect(path) as db:
        assert _attempt_status(db, KEY) == "failed_or_unknown"


def test_accepted_provider_but_failed_local_event_cannot_send_again(setup, monkeypatch):
    path, vid = setup
    calls = fake_provider(monkeypatch)

    def fail(*args, **kwargs):
        raise ValueError("synthetic event failure")

    monkeypatch.setattr(delivery.vor_store, "add_event", fail)
    with pytest.raises(delivery.MessageDeliveryError) as first:
        send(vid)
    assert first.value.reason == "invalid_record"
    with pytest.raises(delivery.MessageDeliveryError) as second:
        send(vid)
    assert second.value.reason == "delivery_uncertain"
    assert len(calls) == 1
    with sqlite3.connect(path) as db:
        assert _attempt_status(db, KEY) == "accepted"
        assert (
            db.execute(
                "SELECT response_json FROM vor_email_requests WHERE request_id=?", (KEY,)
            ).fetchone()[0]
            is None
        )


def test_inflight_request_is_not_dispatched_twice(setup, monkeypatch):
    _, vid = setup
    from threading import Event

    entered = Event()
    release = Event()
    calls = []

    class Accepted:
        def raise_for_status(self):
            pass

    def suspended_post(*args, **kwargs):
        calls.append(kwargs)
        entered.set()
        assert release.wait(10)
        return Accepted()

    monkeypatch.setattr(delivery.httpx, "post", suspended_post)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(send, vid)
        assert entered.wait(10)
        try:
            with pytest.raises(delivery.MessageDeliveryError) as duplicate:
                send(vid)
            assert duplicate.value.reason == "delivery_uncertain"
        finally:
            release.set()
        assert pending.result(timeout=10)["delivery"] == "outgoing"
    assert len(calls) == 1


def test_legacy_unkeyed_email_remains_supported(setup, monkeypatch):
    _, vid = setup
    calls = fake_provider(monkeypatch)
    assert send(vid, request_id=None)["delivery"] == "outgoing"
    assert len(calls) == 1
    assert "Idempotency-Key" not in calls[0]["headers"]


def test_http_replay_and_409_422_idempotency_contract(setup, monkeypatch):
    _, vid = setup
    calls = fake_provider(monkeypatch)
    monkeypatch.setenv("VOR_DEMO_EMAIL_LIMIT", "30")
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        assert (
            client.post("/api/vor/login", json={"password": "fixture-password"}).status_code == 200
        )
        body = {
            "vehicle_id": vid,
            "kind": "email",
            "text": "message one",
            "subject": "Notice",
            "request_id": KEY,
        }
        assert client.post("/api/vor/messages", json=body).status_code == 200
        assert client.post("/api/vor/messages", json=body).status_code == 200
        different = {**body, "text": "different"}
        assert client.post("/api/vor/messages", json=different).status_code == 422

        def timeout(*args, **kwargs):
            raise httpx.ReadTimeout("uncertain provider outcome")

        monkeypatch.setattr(delivery.httpx, "post", timeout)
        uncertain = {**body, "request_id": "123e4567-e89b-42d3-a456-426614174009"}
        assert client.post("/api/vor/messages", json=uncertain).status_code == 502
        response = client.post("/api/vor/messages", json=uncertain)
        assert response.status_code == 409
        assert "verify delivery" in response.json()["detail"]
    assert len(calls) == 1
