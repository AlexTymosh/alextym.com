"""Verify actual mounted routes through HTTP, not FastAPI's internal route list."""

from unittest.mock import Mock

from fastapi.testclient import TestClient
from app.security import sameplace_identity


def test_room_routes_are_mounted_and_fail_closed(monkeypatch):
    from app.main import app

    client = TestClient(app)
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    monkeypatch.setenv("SAMEPLACE_ENABLED", "false")
    verify = Mock(side_effect=AssertionError("Unexpected credential lookup"))
    monkeypatch.setattr(sameplace_identity.firebase, "verify_id_token", verify)
    assert (
        client.get(
            "/api/sameplace/rooms", headers={"Authorization": "Bearer synthetic"}
        ).status_code
        == 404
    )
    verify.assert_not_called()
    assert client.post("/api/sameplace/rooms", content=b"invalid").status_code == 404
    monkeypatch.setenv("SAMEPLACE_ENABLED", "true")
    assert client.get("/api/sameplace/rooms").status_code == 401
    assert client.get("/api/sameplace/identity").status_code == 401
    verify.assert_not_called()
    assert client.delete("/api/preferans/rooms").status_code == 405
