"""Status transport and injected host guard; no external provider access."""

from unittest.mock import Mock

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sameplace.router import router

from app.security import sameplace_access


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(
        router, prefix="/api", dependencies=[Depends(sameplace_access.require_sameplace_member)]
    )
    return TestClient(app)


@pytest.mark.parametrize("flag", [None, "false", "TRUE", "1"])
def test_disabled_does_not_touch_identity(monkeypatch, client, flag):
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    if flag is None:
        monkeypatch.delenv("SAMEPLACE_ENABLED", raising=False)
    else:
        monkeypatch.setenv("SAMEPLACE_ENABLED", flag)
    verify = Mock(side_effect=AssertionError("Unexpected identity lookup"))
    monkeypatch.setattr(sameplace_access, "require_project_access", verify)
    assert client.get("/api/sameplace/status").status_code == 404
    verify.assert_not_called()


def test_lab_disabled_does_not_touch_identity(monkeypatch, client):
    monkeypatch.delenv("PORTFOLIO_LAB_ENABLED", raising=False)
    monkeypatch.setenv("SAMEPLACE_ENABLED", "true")
    verify = Mock(side_effect=AssertionError("Unexpected identity lookup"))
    monkeypatch.setattr(sameplace_access, "require_project_access", verify)
    assert client.get("/api/sameplace/status").status_code == 404
    verify.assert_not_called()


@pytest.mark.parametrize("code", [401, 403, 503])
def test_enabled_denies_unverified_or_unavailable_access(monkeypatch, client, code):
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("SAMEPLACE_ENABLED", "true")
    verify = Mock(side_effect=HTTPException(code))
    monkeypatch.setattr(sameplace_access, "require_project_access", verify)
    assert client.get("/api/sameplace/status").status_code == code
    assert verify.call_args.args[1] == "sameplace"


def test_only_sameplace_grant_scope_and_safe_response(monkeypatch, client):
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("SAMEPLACE_ENABLED", "true")
    verify = Mock(return_value={"uid": "synthetic-private-uid"})
    monkeypatch.setattr(sameplace_access, "require_project_access", verify)
    response = client.get("/api/sameplace/status")
    assert response.status_code == 200
    assert response.json() == {
        "project_id": "sameplace",
        "stage": "foundation",
        "contract_version": 1,
    }
    assert verify.call_args.args[1] == "sameplace"
    assert client.get("/api/sameplace/rooms").status_code == 404
    assert client.post("/api/sameplace/status").status_code == 405
