from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Request
from sameplace.rooms.quota import QuotaCircuit
from sameplace.rooms.rate_limit import RequestLimiter
from app.security import sameplace_identity as adapter


def request(header="Bearer synthetic"):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/sameplace/identity",
            "headers": [(b"authorization", header.encode())],
        }
    )


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("SAMEPLACE_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    verify = Mock(
        return_value={
            "uid": "guest",
            "email": "guest@example.invalid",
            "email_verified": True,
            "firebase": {"sign_in_provider": "password"},
        }
    )
    monkeypatch.setattr(adapter.firebase, "verify_id_token", verify)
    monkeypatch.setattr(adapter.firebase, "load_lab_identity", Mock(return_value=None))
    return verify


def test_room_only_identity_no_global_record(enabled):
    assert adapter.require_sameplace_identity(request()) == {
        "uid": "guest",
        "verified_email": "guest@example.invalid",
        "platform_owner": False,
    }
    adapter.firebase.load_lab_identity.assert_called_once_with("guest")


def test_disabled_never_checks_token(enabled, monkeypatch):
    monkeypatch.setenv("SAMEPLACE_ENABLED", "false")
    with pytest.raises(HTTPException) as error:
        adapter.require_sameplace_identity(request())
    assert error.value.status_code == 404
    enabled.assert_not_called()


@pytest.mark.parametrize(
    "record",
    [
        {"status": "revoked"},
        {
            "schema_version": 1,
            "uid": "guest",
            "status": "active",
            "password_state": "initial",
            "initial_password_expires_at_ms": 1,
        },
    ],
)
def test_existing_lab_denial_is_not_bypassed(enabled, monkeypatch, record):
    monkeypatch.setattr(adapter.firebase, "load_lab_identity", Mock(return_value=record))
    with pytest.raises(HTTPException) as error:
        adapter.require_sameplace_identity(request())
    assert error.value.status_code == 403


def test_unverified_new_account_denied(enabled):
    enabled.return_value["email_verified"] = False
    with pytest.raises(HTTPException) as error:
        adapter.require_sameplace_identity(request())
    assert error.value.status_code == 403


def test_owner_is_derived_only_from_verified_uid(enabled):
    enabled.return_value["uid"] = "owner"
    assert adapter.require_sameplace_identity(request())["platform_owner"] is True
    enabled.return_value["uid"] = "guest"
    assert adapter.require_sameplace_identity(request())["platform_owner"] is False


def test_wrong_credential_scheme_never_falls_back(enabled):
    with pytest.raises(HTTPException) as error:
        adapter.require_sameplace_identity(request("Basic synthetic"))
    assert error.value.status_code == 401
    enabled.assert_not_called()


def test_quota_circuit_and_bounded_rate_limiter():
    now = [0.0]
    circuit = QuotaCircuit(lambda: now[0])
    circuit.observe(RuntimeError("not quota"))
    assert circuit.remaining() == 0
    circuit.observe(type("ResourceExhausted", (Exception,), {})())
    assert circuit.remaining() == 120
    now[0] = 121
    assert circuit.remaining() == 0
    limiter = RequestLimiter(lambda: now[0])
    assert all(limiter.allow("guest") for _ in range(30))
    assert not limiter.allow("guest")
    assert limiter.allow("other")
    now[0] = 181
    assert limiter.allow("guest")
