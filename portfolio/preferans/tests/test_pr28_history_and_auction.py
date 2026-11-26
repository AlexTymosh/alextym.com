"""PR28: latest settlement postings, immutable history and misere-family auction."""

from types import SimpleNamespace

import pytest

from preferans.domain.auction import (
    AuctionAction,
    Bid,
    RuleViolation,
    apply_auction_action,
    can_say_here,
    legal_auction_bids,
    start_auction,
)
from preferans.domain.cards import Suit
from preferans.domain.ledger import ScoreState, _Posting
from preferans.online.table_presentation import notebook, remember_deal
from preferans.online.lobby import room_profiles
from preferans.online.store import FirestoreRooms, StoreError
from test_secure_rooms import FakeDB, transactional


def test_all_latest_deal_postings_are_red_and_history_is_read_only():
    initial = ScoreState.new()
    controls = {}
    post = _Posting(initial, "first")
    post.add_vist(2, 0, 8, "automatic_half_vist")
    post.add_pool(0, 2, "regular_success")
    first = post.finish(initial, 6)
    remember_deal(
        controls,
        "first",
        SimpleNamespace(contract=Bid.regular(6, Suit.CLUBS), declarer=0, is_passout=False),
    )
    sheet = notebook(first, controls)
    assert sheet["exact"]
    assert len(sheet["steps"]) == 1
    assert len([mark for mark in sheet["marks"] if mark.get("latest")]) == 2
    assert sheet["steps"][0]["contract"]["level"] == 6
    assert sheet["steps"][0]["entries"][0]["delta"] == 8
    post = _Posting(first, "second")
    post.add_pool(1, 4, "help_pool")
    post.add_vist(0, 1, 40, "help_vist")
    post.add_pool(2, 4, "help_pool")
    post.add_vist(0, 2, 40, "help_vist")
    second = post.finish(first, 6)
    remember_deal(
        controls,
        "second",
        SimpleNamespace(contract=Bid.regular(9, Suit.CLUBS), declarer=0, is_passout=False),
    )
    after = notebook(second, controls)
    assert len(after["steps"]) == 2
    assert len([mark for mark in after["marks"] if mark.get("latest")]) == 4
    assert after["steps"][1]["contract"]["level"] == 9
    assert notebook(first, controls) == sheet
    assert second.vists[0] == (0, 40, 40)


def test_misere_bidder_cannot_switch_to_regular_or_hold():
    st = start_auction(0)
    st = apply_auction_action(st, 1, AuctionAction.place(Bid.misere()))
    st = apply_auction_action(st, 2, AuctionAction.place(Bid.regular(9, Suit.CLUBS)))
    st = apply_auction_action(st, 0, AuctionAction.pass_turn())
    assert legal_auction_bids(st, 1) == (Bid.misere_no_widow(),)
    assert not can_say_here(st, 1)
    for action in (
        AuctionAction.here(),
        AuctionAction.place(Bid.regular(10, Suit.CLUBS)),
        AuctionAction.place(Bid.ten_no_widow(None)),
    ):
        with pytest.raises(RuleViolation):
            apply_auction_action(st, 1, action)
    st = apply_auction_action(st, 1, AuctionAction.place(Bid.misere_no_widow()))
    st = apply_auction_action(st, 2, AuctionAction.place(Bid.regular(10, Suit.SPADES)))
    assert legal_auction_bids(st, 1) == ()


def test_email_lookup_only_after_room_membership_and_only_for_missing_name():
    db = FakeDB()
    rid = "a" * 32
    db.docs[f"preferans_rooms/{rid}"] = {"id": rid, "status": "lobby", "seats": ["a", "b", None]}
    db.docs["portfolio_lab_profiles/a"] = {"first_name": "Player"}
    calls = []

    def lookup(uid):
        calls.append(uid)
        return "test@example.invalid"

    with pytest.raises(StoreError):
        room_profiles(db, rid, "stranger", email_lookup=lookup)
    assert not calls
    result = room_profiles(db, rid, "a", email_lookup=lookup)
    assert calls == ["b"]
    assert result["profiles"][1]["email"] == "test@example.invalid"
    assert "email" not in result["profiles"][0]
    assert "email" not in result["profiles"][2]


@pytest.mark.parametrize("target", [1, 3, 39, 42, 1000])
def test_room_config_rejects_invalid_pool_size(monkeypatch, target):
    monkeypatch.setenv("PREFERANS_REALTIME_ENABLED", "false")
    api = FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))
    room = api.create("a", "pr28-create-01", require_ready=True)["room_id"]
    with pytest.raises(StoreError) as error:
        api.command(room, "a", "pr28-config-01", 0, "lobby_config", {"dealer": 1, "target": target})
    assert error.value.code == 422
