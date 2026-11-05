"""HTTP-neutral Fleet message delivery and error-mapping contracts.

No real provider calls or persistent database files are used in this module.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fleet_hub.api import vor
from fleet_hub.services import message_delivery as delivery


def _post(*, kind="internal", ticket_id=None, subject=None, text="Message"):
    return delivery.post_message(
        vehicle_id=7, ticket_id=ticket_id, kind=kind, text=text, subject=subject
    )


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch):
    events = []
    finishes = []
    reservations = []

    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "false")
    monkeypatch.setattr(delivery.vor_store, "validate_vehicle_ticket", lambda *args: "AB12 CDE")
    monkeypatch.setattr(
        delivery.vor_store,
        "subscriber_emails",
        lambda *args: ["one@unit.example", "two@unit.example"],
    )

    def add_event(*args, **kwargs):
        events.append((args, kwargs))
        return 34

    def reserve(count, limit):
        reservations.append((count, limit))
        return 12

    monkeypatch.setattr(delivery.vor_store, "add_event", add_event)
    monkeypatch.setattr(delivery.vor_store, "reserve_email_delivery", reserve)
    monkeypatch.setattr(
        delivery.vor_store,
        "finish_email_delivery",
        lambda rid, state: finishes.append((rid, state)),
    )
    monkeypatch.setattr(
        delivery.httpx, "post", lambda *args, **kwargs: pytest.fail("Unintended provider call")
    )
    return events, reservations, finishes


def _enable_real_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOR_DEMO_SEND_REAL_EMAIL", "true")
    monkeypatch.setenv("VOR_DEMO_ALLOWED_RECIPIENTS", "")
    monkeypatch.setenv("VOR_DEMO_ALLOWED_EMAIL_DOMAINS", "unit.example")
    monkeypatch.setenv("VOR_DEMO_EMAIL_LIMIT", "2")
    monkeypatch.setenv("RESEND_API_KEY", "not-a-real-key")
    monkeypatch.setenv("VOR_DEMO_FROM_EMAIL", "fleet@verified.example")
    monkeypatch.setenv("VOR_DEMO_PUBLIC_URL", "https://fleet.example/hub")


def test_internal_message_does_not_consume_email_quota(store):
    events, reservations, finishes = store
    result = _post(text="Private staff note")
    assert result == {"id": 34, "delivery": "internal", "recipient_count": 0, "recipients": []}
    assert not reservations and not finishes
    args, kwargs = events[0]
    assert args[:4] == (7, None, "internal", "Private staff note")
    assert kwargs == {"subject": None, "recipient": None, "direction": None}


def test_simulated_email_preserves_subject_and_recipients(store):
    events, reservations, _ = store
    result = _post(kind="email", ticket_id="PS000100", subject="Notice")
    assert result == {
        "id": 34,
        "delivery": "simulated_outgoing",
        "recipient_count": 2,
        "recipients": ["one@unit.example", "two@unit.example"],
    }
    assert events[0][1] == {
        "subject": "[AB12 CDE][PS000100] Notice",
        "recipient": "one@unit.example,two@unit.example",
        "direction": "simulated_outgoing",
    }
    assert not reservations


def test_real_provider_receives_one_bcc_notice_and_updates_quota(store, monkeypatch):
    events, reservations, finishes = store
    _enable_real_email(monkeypatch)
    calls = []

    class Accepted:
        def raise_for_status(self):
            pass

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Accepted()

    monkeypatch.setattr(delivery.httpx, "post", fake_post)
    result = _post(kind="email", ticket_id="PS000100", subject="Change", text="Internal details")
    assert result["delivery"] == "outgoing"
    assert reservations == [(2, 2)]
    assert finishes == [(12, "accepted")]
    assert len(calls) == 1
    url, request = calls[0]
    assert url == "https://api.resend.com/emails"
    assert request["timeout"] == 12
    assert request["json"]["to"] == ["one@unit.example"]
    assert request["json"]["bcc"] == ["two@unit.example"]
    assert request["json"]["subject"] == "[AB12 CDE][PS000100] Change"
    assert "Internal details" not in request["json"]["text"]
    assert "https://fleet.example/hub" in request["json"]["text"]
    assert events[0][1]["direction"] == "outgoing"


def test_provider_error_marks_reservation_unknown_without_event(store, monkeypatch):
    events, reservations, finishes = store
    _enable_real_email(monkeypatch)

    def fail(*args, **kwargs):
        raise httpx.ConnectError("connection error")

    monkeypatch.setattr(delivery.httpx, "post", fail)
    with pytest.raises(delivery.MessageDeliveryError) as exc:
        _post(kind="email")
    assert exc.value.reason == "provider_unavailable"
    assert reservations == [(2, 2)]
    assert finishes == [(12, "failed_or_unknown")]
    assert events == []


def test_quota_rejection_makes_no_provider_request(store, monkeypatch):
    events, _, finishes = store
    _enable_real_email(monkeypatch)

    def exhausted(*args):
        raise ValueError("limit reached")

    monkeypatch.setattr(delivery.vor_store, "reserve_email_delivery", exhausted)
    with pytest.raises(delivery.MessageDeliveryError) as exc:
        _post(kind="email")
    assert exc.value.reason == "daily_quota_exceeded"
    assert not finishes and not events


@pytest.mark.parametrize(
    ("emails", "reason"),
    [([], "no_subscribers"), (["not-email"], "invalid_subscriber_email")],
)
def test_invalid_subscriber_directory_rejected_before_quota(store, monkeypatch, emails, reason):
    _, reservations, _ = store
    monkeypatch.setattr(delivery.vor_store, "subscriber_emails", lambda *_: emails)
    with pytest.raises(delivery.MessageDeliveryError) as exc:
        _post(kind="email")
    assert exc.value.reason == reason
    assert not reservations


def test_unapproved_recipient_is_blocked_before_quota(store, monkeypatch):
    _, reservations, _ = store
    _enable_real_email(monkeypatch)
    monkeypatch.setenv("VOR_DEMO_ALLOWED_EMAIL_DOMAINS", "different.example")
    with pytest.raises(delivery.MessageDeliveryError) as exc:
        _post(kind="email")
    assert exc.value.reason == "recipient_not_allowed"
    assert not reservations


def test_accepted_provider_but_failed_event_remains_visible_as_known_risk(store, monkeypatch):
    """Characterize ordering; a future idempotency/reconciliation change is separate."""
    _, reservations, finishes = store
    _enable_real_email(monkeypatch)
    calls = []

    class Accepted:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        delivery.httpx, "post", lambda *a, **k: (calls.append((a, k)), Accepted())[1]
    )

    def fail_event(*args, **kwargs):
        raise ValueError("event write rejected")

    monkeypatch.setattr(delivery.vor_store, "add_event", fail_event)
    with pytest.raises(delivery.MessageDeliveryError) as exc:
        _post(kind="email")
    assert exc.value.reason == "invalid_record"
    assert exc.value.detail == "event write rejected"
    assert reservations == [(2, 2)]
    assert finishes == [(12, "accepted")]
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("no_subscribers", 422),
        ("invalid_subscriber_email", 422),
        ("policy_missing", 503),
        ("recipient_not_allowed", 403),
        ("mail_config_missing", 503),
        ("public_url_unreachable", 503),
        ("daily_quota_exceeded", 429),
        ("provider_unavailable", 502),
        ("invalid_record", 422),
    ],
)
def test_http_adapter_preserves_error_statuses(monkeypatch, reason, expected):
    monkeypatch.setenv("VOR_DEMO_ENABLED", "true")
    monkeypatch.setenv("VOR_DEMO_PASSWORD", "fixture-password")

    def failure(**kwargs):
        raise delivery.MessageDeliveryError(
            reason, "dynamic failure" if reason == "invalid_record" else None
        )

    monkeypatch.setattr(delivery, "post_message", failure)
    app = FastAPI()
    app.include_router(vor.router, prefix="/api")
    with TestClient(app) as client:
        assert (
            client.post("/api/vor/login", json={"password": "fixture-password"}).status_code == 200
        )
        response = client.post(
            "/api/vor/messages", json={"vehicle_id": 7, "kind": "email", "text": "Hi"}
        )
        assert response.status_code == expected, response.text
        assert response.json()["detail"] == (
            "dynamic failure" if reason == "invalid_record" else vor._MESSAGE_HTTP_ERRORS[reason][1]
        )
