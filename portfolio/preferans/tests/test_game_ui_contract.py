"""API contract tests for PR 5, using PR 4's memory-only fake Firestore."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from preferans.domain.cards import FULL_DECK, deal
from preferans.domain.game import start_game
from preferans.domain.ledger import ScoreState
from preferans.online.router import room_invitation
from preferans.online.store import FirestoreRooms, StoreError
from preferans.online.views import seat_view
from test_secure_rooms import FakeDB, transactional


def _service() -> FirestoreRooms:
    return FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))


def test_invitation_works_before_join_without_leaking_secrets():
    service = _service()
    created = service.create("a", "create-0001")
    rid = created["room_id"]
    result = service.invitation(rid, "b")
    assert result == {
        "room_id": rid,
        "version": 0,
        "status": "lobby",
        "occupied": [True, False, False],
    }
    assert not any(k in str(result) for k in ["game", "uid", "admin", "hand", "discard"])
    assert service.join(rid, "b", "join-b-0001", result["version"])["version"] == 1
    latest = service.invitation(rid, "c")
    assert latest["version"] == 1
    assert service.join(rid, "c", "join-c-0001", latest["version"])["version"] == 2
    service.start(rid, "a", "start-a-0001", 2, owner=False)
    with pytest.raises(StoreError) as exc:
        service.invitation(rid, "d")
    assert exc.value.code == 404


def test_invitation_endpoint_blocks_view_role_even_if_room_id_known():
    request = SimpleNamespace(state=SimpleNamespace(portfolio_lab_role="View"))
    with pytest.raises(HTTPException) as exc:
        room_invitation("a" * 32, request)
    assert exc.value.status_code == 403


def test_public_projection_includes_turn_controls_but_no_other_hidden_hand():
    game = start_game(deal(FULL_DECK, 2))
    room = {
        "id": "a" * 32,
        "status": "playing",
        "seats": ["a", "b", "c"],
        "admin_uid": "a",
        "game_id": "game",
    }
    result = seat_view(room, game, ScoreState.new(), "a", 3)
    assert result["dealer"] == 2
    assert result["first_hand"] == 0
    assert result["controller"] == 0
    assert result["is_passout"] is False
    assert result["played_tricks"] == 0
    assert result["can_say_here"] is False
    assert result["legal_contracts"] == []
    assert result["score"]["target"] == ScoreState.new().target
    assert "hands" not in result and "discarded" not in result
    assert "private" not in result and "uid" not in result
    observer = seat_view(room, game, ScoreState.new(), "platform-owner", 3, owner=True)
    assert "hand" not in observer and "legal_cards" not in observer
    assert "legal_contracts" not in observer


def test_three_player_room_passout_from_lobby_to_settlement():
    """Real domain/room actions through fake transactions, not a hand-picked projection."""
    service = _service()
    uid = ["a", "b", "c"]
    rid = service.create(uid[0], "create-rooms-1")["room_id"]
    for seat in (1, 2):
        lobby = service.invitation(rid, uid[seat])
        service.join(rid, uid[seat], f"join-player-{seat}", lobby["version"])
    service.start(rid, uid[0], "start-player-0", 2, owner=False)
    initial = service.view(rid, uid[0])
    assert initial["phase"] == "auction"
    for index in range(3):
        current = service.view(rid, uid[0])
        actor = current["turn"]
        assert actor in (0, 1, 2)
        service.command(rid, uid[actor], f"pass-000{index}", current["version"], "pass", {})
    assert service.view(rid, uid[0])["is_passout"] is True
    for index in range(30):
        current = service.view(rid, uid[0])
        assert current["phase"] == "play"
        seat = current["turn"]
        assert seat in (0, 1, 2)
        hand = service.view(rid, uid[seat])
        assert hand["controller"] == seat
        assert hand["legal_cards"]
        card = hand["legal_cards"][0]
        response = service.command(
            rid,
            uid[seat],
            f"played-card-{index:03d}",
            current["version"],
            "play",
            {"owner": seat, "card": card},
        )
        assert response["version"] == current["version"] + 1
    finished = service.view(rid, uid[0])
    assert finished["phase"] == "finished"
    assert finished["status"] == "awaiting_settlement"
    assert sum(finished["tricks_won"]) == 10
    before = finished["score"]
    result = service.settle(
        rid,
        uid[0],
        "settle-00001",
        finished["version"],
        {"regular_route": "pool", "passout_routes": ["pool", "pool", "pool"]},
        owner=False,
    )
    after = service.view(rid, uid[0])
    assert result["version"] == finished["version"] + 1
    assert after["score"] != before
    assert after["status"] in ("between", "closed")
    if after["status"] == "between":
        service.start(rid, uid[0], "start-next-1", after["version"], owner=False)
        assert service.view(rid, uid[1])["phase"] == "auction"
    history = service.events(rid, uid[1])
    assert len(history["events"]) > 0
    assert not any("private" in str(row) or "discarded" in str(row) for row in history["events"])
