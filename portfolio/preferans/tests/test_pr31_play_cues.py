"""Regression: exact winning-bid concession, private cues, and unchanged play rights."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from preferans.domain.auction import Bid, RuleViolation
from preferans.domain.cards import Suit
from preferans.domain.scoring import settle_game
from preferans.domain.ledger import ScoreState
from preferans.online.codec import decode, encode
from preferans.online.commands import apply_command
from preferans.online.defense_hints import decorated_view, receive_hint
from preferans.online.store import FirestoreRooms, StoreError
from test_declaration_polish import declaration
from test_secure_rooms import FakeDB, transactional


@pytest.mark.parametrize("level,cost", [(6, 2), (7, 4), (8, 6), (9, 8), (10, 10)])
def test_concession_uses_exact_winning_bid(level, cost):
    state = replace(declaration(), winning_bid=Bid.regular(level, Suit.HEARTS))
    finished = apply_command(state, 0, "without_three", {})
    assert finished.contract == state.winning_bid
    assert finished.turn is None and not any(finished.defense)
    score = settle_game(ScoreState.new(), finished, f"concede-{level}")
    assert score.hill == (3 * cost, 0, 0)
    assert score.pool == (0, 0, 0)
    assert score.vists == ((0, 0, 0),) * 3
    with pytest.raises(RuleViolation):
        apply_command(
            state, 0, "without_three", {"bid": {"kind": "regular", "level": level, "suit": "S"}}
        )


def test_eight_concession_is_an_atomic_idempotent_store_transaction(monkeypatch):
    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    api = FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))
    rid = api.create("a", "pr31-create")["room_id"]
    api.join(rid, "b", "pr31-join-b", 0)
    api.join(rid, "c", "pr31-join-c", 1)
    record = api.db.docs[f"preferans_rooms/{rid}/private/current"]
    record["score"] = encode(replace(decode(record["score"]), passout_level=8))
    api.start(rid, "a", "pr31-start", 2, False)
    initial = api.view(rid, "a")
    uid = "abc"[initial["turn"]]
    bid = {"kind": "regular", "level": 8, "suit": "H"}
    api.command(rid, uid, "pr31-bid", initial["version"], "bid", {"bid": bid})
    for n in range(2):
        view = api.view(rid, "a")
        api.command(rid, "abc"[view["turn"]], f"pr31-pass-{n}", view["version"], "pass", {})
    view = api.view(rid, uid)
    api.command(rid, uid, "pr31-discard", view["version"], "discard", {"cards": view["widow"]})
    view = api.view(rid, uid)
    assert view["phase"] == "declare"
    result = api.command(rid, uid, "pr31-concede", view["version"], "without_three", {})
    assert result["status"] == "between"
    assert api.command(rid, uid, "pr31-concede", view["version"], "without_three", {}) == result
    for player in "abc":
        final = api.view(rid, player)
        assert final["end_reason"] == "without_three"
        assert final["score"]["hill"]["abc".index(uid)] == 18
        assert sum(final["score"]["hill"]) == 18
        assert final["score"]["pool"] == [0, 0, 0]
        assert final["score"]["vists"] == [[0, 0, 0]] * 3
        assert final["score"]["passout_level"] == 8
    with pytest.raises(StoreError):
        api.command(rid, uid, "pr31-concede-again", result["version"], "without_three", {})


def fixture(kind="misere", mode="open"):
    cards = [{"suit": "S", "rank": 14}, {"suit": "C", "rank": 7}, {"suit": "D", "rank": 8}]
    views = {}
    for seat, uid in enumerate("abc"):
        views[uid] = {
            "room_id": "a" * 32,
            "game_id": "g",
            "version": 10,
            "my_seat": seat,
            "declarer": 0,
            "status": "playing",
            "phase": "play",
            "mode": mode,
            "contract": {"kind": kind},
            "defense": [None, "vist", "pass"],
            "hand": [cards[seat]],
            "open_hands": [{"seat": i, "cards": [cards[i]]} for i in (1, 2)]
            if mode == "open"
            else [],
        }
    return SimpleNamespace(
        views=views, revision=10, defense_hints={}, defense_hint_scope=None
    ), cards


@pytest.mark.parametrize("kind", ["regular", "misere", "misere_no_widow"])
def test_defender_can_raise_partner_card_without_changing_authoritative_state(kind):
    room, cards = fixture(kind)
    frame = {
        "type": "defense_hint",
        "protocol": 1,
        "game_id": "g",
        "version": 10,
        "owner": 2,
        "card": cards[2],
        "raised": True,
    }
    assert receive_hint(room, "b", frame)
    for uid in "bc":
        assert decorated_view(room, room.views[uid])["defense_hints"] == [
            {"owner": 2, "card": cards[2]}
        ]
    assert "defense_hints" not in decorated_view(room, room.views["a"])
    assert "defense_hints" not in room.views["b"]
    assert not receive_hint(room, "a", frame)
    assert not receive_hint(room, "b", {**frame, "owner": 0, "card": cards[0]})
    assert not receive_hint(room, "b", {**frame, "version": 9})
    assert not receive_hint(room, "b", {**frame, "card": {"suit": "H", "rank": 14}})
    assert receive_hint(room, "c", {**frame, "raised": False})
    assert decorated_view(room, room.views["b"])["defense_hints"] == []
    assert receive_hint(room, "b", frame)
    room.revision = 11
    for view in room.views.values():
        view["version"] = 11
    assert decorated_view(room, room.views["c"])["defense_hints"] == []


def test_closed_hand_is_never_disclosed_by_a_cue():
    room, cards = fixture("regular", "closed")
    frame = {
        "type": "defense_hint",
        "protocol": 1,
        "game_id": "g",
        "version": 10,
        "owner": 1,
        "card": cards[1],
        "raised": True,
    }
    assert not receive_hint(room, "b", frame)
    assert decorated_view(room, room.views["c"])["defense_hints"] == []
    room.views["b"]["controls"] = {"paused": True}
    assert "defense_hints" not in decorated_view(room, room.views["b"])
