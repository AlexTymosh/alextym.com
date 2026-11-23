"""Host auth fail-closed and grant separation for the Preferans router."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.security.preferans_access import require_preferans_member


def test_room_routes_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PREFERANS_ROOMS_ENABLED", raising=False)
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    request = Mock()
    with pytest.raises(HTTPException) as error:
        require_preferans_member(request)
    assert error.value.status_code == 404


def test_host_guard_rejects_invalid_signed_session(monkeypatch):
    monkeypatch.setenv("PREFERANS_ROOMS_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setattr(
        "app.security.preferans_access.require_project_access",
        lambda *args: (_ for _ in ()).throw(HTTPException(401)),
    )
    with pytest.raises(HTTPException) as error:
        require_preferans_member(Mock())
    assert error.value.status_code == 401


def test_granted_identity_is_attached_only_after_host_verification(monkeypatch):
    monkeypatch.setenv("PREFERANS_ROOMS_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_ENABLED", "true")
    monkeypatch.setenv("PORTFOLIO_LAB_OWNER_UID", "owner")
    monkeypatch.setattr(
        "app.security.preferans_access.require_project_access", lambda *args: {"uid": "guest"}
    )
    request = Mock()
    require_preferans_member(request)
    assert request.state.preferans_uid == "guest"
    assert request.state.preferans_owner is False
