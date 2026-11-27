"""Mounted host smoke via HTTP; no Firebase calls or lifespan side effects."""

from unittest.mock import Mock
from fastapi.testclient import TestClient
from app.security import sameplace_identity


def test_social_routes_fail_closed_on_actual_host(monkeypatch):
    from app.main import app

    client = TestClient(app)
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    monkeypatch.setenv("SAMEPLACE_ENABLED", "false")
    verify = Mock(side_effect=AssertionError("Unexpected identity lookup"))
    monkeypatch.setattr(sameplace_identity.firebase, "verify_id_token", verify)
    assert (
        client.get(
            "/api/sameplace/social/me", headers={"Authorization": "Bearer synthetic"}
        ).status_code
        == 404
    )
    assert client.post("/api/sameplace/rooms/friday/ticket", content=b"invalid").status_code == 404
    monkeypatch.setenv("SAMEPLACE_ENABLED", "true")
    assert client.get("/api/sameplace/social/me").status_code == 401
    assert client.get("/api/sameplace/rooms/friday/chat").status_code == 401
    verify.assert_not_called()
    assert client.delete("/api/preferans/rooms").status_code == 405
