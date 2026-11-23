"""PR6 clock/voting/accounting security regression with a controllable server clock."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from preferans.domain.auction import AuctionAction, Bid
from preferans.domain.cards import FULL_DECK, Suit, deal
from preferans.domain.game import auction_action, start_game
from preferans.domain.ledger import ScoreState
from preferans.online.controls import (
    ControlError,
    TIMER_MS,
    VOTE_MS,
    acting_seat,
    fresh,
    start_counter,
    timer_cost,
)
from preferans.online.store import FirestoreRooms, StoreError
from test_secure_rooms import FakeDB, transactional


def service():
    clock = [1_800_000_000_000]
    api = FirestoreRooms(
        FakeDB(),
        firestore_module=SimpleNamespace(transactional=transactional),
        now_ms=lambda: clock[0],
    )
    created = api.create("a", "create-room-001")
    rid = created["room_id"]
    api.join(rid, "b", "join-room-b-01", 0)
    api.join(rid, "c", "join-room-c-01", 1)
    api.start(rid, "a", "start-room-01", 2, False)
    return api, rid, clock


def pulse_all(api, rid, clock):
    for seat, uid in enumerate("abc"):
        current = api.view(rid, "a")["version"]
        api.command(rid, uid, f"pulse{seat}-{clock[0]}", current, "pulse", {})


def test_undo_vote_after_latest_bid_does_not_erase_audit():
    api, rid, clock = service()
    view = api.view(rid, "a")
    seat = view["turn"]
    player = "abc"[seat]
    bid = {"kind": "regular", "level": 6, "suit": "S"}
    done = api.command(rid, player, "bid-before-undo", view["version"], "bid", {"bid": bid})
    # A heartbeat is NOT a new bid and must not cancel undo eligibility.
    pulse_all(api, rid, clock)
    seen = api.view(rid, player)
    assert seen["controls"]["can_request_undo"]
    opened = api.command(
        rid,
        player,
        "request-undo-01",
        seen["version"],
        "undo_request",
        {"reason": "Случайно нажал ставку"},
    )
    assert opened["version"] > done["version"]
    with pytest.raises(StoreError) as exc:
        api.command(rid, "abc"[(seat + 1) % 3], "wrong-bid-0001", opened["version"], "pass", {})
    assert exc.value.code == 409
    current = api.view(rid, "a")
    for n, voter in enumerate(("abc"[(seat + 1) % 3], "abc"[(seat + 2) % 3])):
        api.command(
            rid, voter, f"approve-undo-{n}", current["version"], "undo_vote", {"approve": True}
        )
        current = api.view(rid, "a")
    assert current["high_bid"] is None
    assert current["turn"] == seat
    assert not current["controls"]["undo"]
    events = api.events(rid, "a")["events"]
    assert any(e["action"] == "bid" for e in events)
    assert any(
        e["action"] == "undo_vote" and e["data"].get("outcome") == "accepted" for e in events
    )
    assert "hands" not in str(events)


def test_undo_rejected_or_timeout_keeps_bid():
    api, rid, clock = service()
    before = api.view(rid, "a")
    player = "abc"[before["turn"]]
    bid = {"kind": "regular", "level": 6, "suit": "S"}
    api.command(rid, player, "bid-before-reject", before["version"], "bid", {"bid": bid})
    pulse_all(api, rid, clock)
    current = api.view(rid, player)
    api.command(
        rid,
        player,
        "request-reject",
        current["version"],
        "undo_request",
        {"reason": "Ошибка в ставке"},
    )
    current = api.view(rid, "a")
    voter = next(uid for uid in "abc" if uid != player)
    api.command(rid, voter, "reject-undo-01", current["version"], "undo_vote", {"approve": False})
    assert api.view(rid, "a")["high_bid"] == bid
    current = api.view(rid, player)
    # Request can be made again while no new gameplay action was accepted.
    api.command(
        rid,
        player,
        "request-timeout",
        current["version"],
        "undo_request",
        {"reason": "Ошибка в ставке"},
    )
    clock[0] += VOTE_MS
    api.db.docs[f"preferans_rooms/{rid}/private/current"]["controls"]["presence"] = [clock[0]] * 3
    pulse_all(api, rid, clock)
    assert api.view(rid, "a")["controls"]["undo"] is None
    assert api.view(rid, "a")["high_bid"] == bid


def test_counter_exact_boundary_and_no_duplicate_counter():
    api, rid, clock = service()
    pulse_all(api, rid, clock)
    current = api.view(rid, "a")
    target = current["controller"] if current["phase"] == "play" else current["turn"]
    opponent = (target + 1) % 3
    start = api.command(
        rid, "abc"[opponent], "counter-open-01", current["version"], "counter_start", {}
    )
    with pytest.raises(StoreError) as exc:
        api.command(
            rid, "abc"[(target + 2) % 3], "counter-open-02", start["version"], "counter_start", {}
        )
    assert exc.value.code == 409
    base = api.view(rid, "a")["score"]["hill"][target]
    clock[0] += TIMER_MS - 1
    api.db.docs[f"preferans_rooms/{rid}/private/current"]["controls"]["presence"] = [clock[0]] * 3
    current = api.view(rid, "a")
    # Target acts one ms before deadline: no penalty, timer stops.
    api.command(rid, "abc"[target], "pass-near-deadline", current["version"], "pass", {})
    assert api.view(rid, "a")["score"]["hill"][target] == base
    assert api.view(rid, "a")["controls"]["counter"] is None


def test_counter_two_periods_and_next_period_with_heartbeat():
    api, rid, clock = service()
    pulse_all(api, rid, clock)
    current = api.view(rid, "a")
    target = current["turn"]
    opp = (target + 1) % 3
    api.command(rid, "abc"[opp], "counter-start-01", current["version"], "counter_start", {})
    clock[0] += TIMER_MS * 2
    # Simulate presence maintained across the two full intervals.
    state_key = f"preferans_rooms/{rid}/private/current"
    api.db.docs[state_key]["controls"]["presence"] = [clock[0]] * 3
    current = api.view(rid, "a")
    response = api.command(rid, "abc"[opp], "pulse-run-timer", current["version"], "pulse", {})
    seen = api.view(rid, "a")
    assert seen["score"]["hill"][target] == 12
    assert seen["controls"]["counter"]["periods"] == 2
    assert seen["controls"]["counter"]["deadline_ms"] == clock[0] + TIMER_MS
    history = api.events(rid, "a")["events"]
    assert (
        sum(e["data"].get("periods", 0) for e in history if e["action"] == "counter_expired") == 2
    )
    assert response["version"] > current["version"]


def test_disconnection_freezes_counter_until_all_return():
    api, rid, clock = service()
    pulse_all(api, rid, clock)
    state = api.view(rid, "a")
    target = state["turn"]
    opponent = (target + 1) % 3
    api.command(rid, "abc"[opponent], "counter-start-pause", state["version"], "counter_start", {})
    clock[0] += 400_000
    # Trigger reconciliation while all three presence leases are stale.
    current = api.view(rid, "a")
    api.command(rid, "abc"[opponent], "pulse-stale-01", current["version"], "pulse", {})
    frozen = api.view(rid, "a")
    assert frozen["controls"]["paused"] is True
    score = frozen["score"]["hill"][target]
    clock[0] += 700_000
    for seat, uid in enumerate("abc"):
        current = api.view(rid, "a")
        api.command(rid, uid, f"heartbeat-resume-{seat}", current["version"], "pulse", {})
    assert api.view(rid, "a")["controls"]["paused"] is False
    assert api.view(rid, "a")["score"]["hill"][target] == score


def test_admin_adjustment_is_audited_and_cannot_close_game():
    api, rid, clock = service()
    current = api.view(rid, "a")
    args = {
        "field": "hill",
        "seat": 1,
        "against": None,
        "delta": 5,
        "reason": "Ошибку в расчёте исправил администратор",
    }
    with pytest.raises(StoreError) as exc:
        api.admin_adjust(rid, "b", "bad-admin-0001", current["version"], args, False)
    assert exc.value.code == 403
    result = api.admin_adjust(rid, "a", "admin-hill-0001", current["version"], args, False)
    assert api.admin_adjust(rid, "a", "admin-hill-0001", current["version"], args, False) == result
    now = api.view(rid, "b")
    assert now["score"]["hill"][1] == 5
    assert now["controls"]["adjustments"][-1]["reason"] == args["reason"]
    assert now["controls"]["adjustments"][-1]["before"] == 0
    assert now["controls"]["adjustments"][-1]["after"] == 5
    history = api.events(rid, "c")["events"]
    assert any(row["action"] == "score_adjust" for row in history)
    with pytest.raises(StoreError) as exc:
        api.admin_adjust(
            rid,
            "a",
            "admin-bad-pool",
            now["version"],
            {**args, "field": "pool", "delta": 21},
            False,
        )
    assert exc.value.code == 422
    with pytest.raises(StoreError) as exc:
        api.admin_adjust(
            rid,
            "a",
            "admin-bad-vist",
            now["version"],
            {**args, "field": "vist", "against": 1, "seat": 1},
            False,
        )
    assert exc.value.code == 422
    # No fake rollbacks of committed outcomes; inverse adjustment leaves an audit trail.
    api.admin_adjust(
        rid, "a", "admin-hill-compensate", now["version"], {**args, "delta": -5}, False
    )
    assert api.view(rid, "b")["score"]["hill"][1] == 0
    assert len(api.view(rid, "a")["controls"]["adjustments"]) == 2


def test_cannot_edit_closed_game_even_as_platform_owner():
    api, rid, clock = service()
    doc = f"preferans_rooms/{rid}"
    api.db.docs[doc]["status"] = "closed"
    version = api.db.docs[doc]["version"]
    args = {
        "field": "hill",
        "seat": 1,
        "against": None,
        "delta": 5,
        "reason": "Позднее исправление",
    }
    with pytest.raises(StoreError) as exc:
        api.admin_adjust(rid, "owner", "too-late-001", version, args, True)
    assert exc.value.code == 409


def test_timer_costs_follow_house_contract_costs():
    game = start_game(deal(FULL_DECK, 2), 7)
    assert timer_cost(game, ScoreState.new()) == 4
    state = auction_action(game, game.turn, AuctionAction.place(Bid.regular(8, Suit.SPADES)))
    assert timer_cost(state, ScoreState.new()) == 6
    assert acting_seat(state) == state.turn
    control = fresh()
    timer = start_counter(control, state, ScoreState.new(), (state.turn + 1) % 3, 0)
    assert timer["penalty"] == 18
    with pytest.raises(ControlError) as exc:
        start_counter(control, state, ScoreState.new(), (state.turn + 2) % 3, 0)
    assert exc.value.status == 409


def test_card_undo_restores_last_card_before_next_actor_moves():
    api, rid, clock = service()
    for index in range(3):
        current = api.view(rid, "a")
        seat = current["turn"]
        api.command(rid, "abc"[seat], f"pass-passout-{index}", current["version"], "pass", {})
    before = api.view(rid, "a")
    seat = before["turn"]
    player = "abc"[seat]
    card = api.view(rid, player)["legal_cards"][0]
    api.command(
        rid, player, "play-before-undo", before["version"], "play", {"card": card, "owner": seat}
    )
    now = api.view(rid, player)
    assert now["controls"]["can_request_undo"] is True
    assert len(now["trick"]) == 1
    pulse_all(api, rid, clock)
    now = api.view(rid, player)
    api.command(
        rid,
        player,
        "undo-play-request",
        now["version"],
        "undo_request",
        {"reason": "Сыграл неверную карту"},
    )
    for n in range(1, 3):
        now = api.view(rid, player)
        api.command(
            rid,
            "abc"[(seat + n) % 3],
            f"card-vote-{n:02d}",
            now["version"],
            "undo_vote",
            {"approve": True},
        )
    restored = api.view(rid, player)
    assert restored["phase"] == before["phase"]
    assert restored["trick"] == before["trick"]
    assert restored["hand"] == api.view(rid, player)["hand"]
    assert any(x == card for x in restored["hand"])
    assert restored["turn"] == seat


def test_room_policy_numeric_only_before_first_deal():
    clock = [1_800_000_000_000]
    api = FirestoreRooms(
        FakeDB(),
        firestore_module=SimpleNamespace(transactional=transactional),
        now_ms=lambda: clock[0],
    )
    rid = api.create("a", "create-room-preset")["room_id"]
    policy = {"counter_seconds": 240, "counter_multiplier": 4, "undo_seconds": 90}
    result = api.command(rid, "a", "configure-policy-01", 0, "preset", policy)
    assert result["version"] == 1
    # Future clients see the ruleset numeric snapshot without private hands.
    state = api.view(rid, "a")
    assert state["controls"]["policy"] == policy
    with pytest.raises(StoreError) as exc:
        api.command(
            rid, "a", "configure-policy-bad", 1, "preset", {**policy, "counter_seconds": 10}
        )
    assert exc.value.code == 422
    api.join(rid, "b", "join-room-b-policy", 1)
    api.join(rid, "c", "join-room-c-policy", 2)
    api.start(rid, "a", "start-room-policy", 3, False)
    current = api.view(rid, "a")
    with pytest.raises(StoreError) as exc:
        api.command(rid, "a", "configure-policy-late", current["version"], "preset", policy)
    assert exc.value.code == 409
    pulse_all(api, rid, clock)
    current = api.view(rid, "a")
    seat = current["turn"]
    opponent = (seat + 1) % 3
    api.command(rid, "abc"[opponent], "custom-counter-01", current["version"], "counter_start", {})
    timer = api.view(rid, "a")["controls"]["counter"]
    assert timer["penalty"] == 8
    assert timer["period_ms"] == 240_000


def test_control_projection_never_returns_private_undo_checkpoint():
    api, rid, _ = service()
    current = api.view(rid, "a")
    seat = current["turn"]
    api.command(
        rid,
        "abc"[seat],
        "bid-secret-snapshot",
        current["version"],
        "bid",
        {"bid": {"kind": "regular", "level": 6, "suit": "S"}},
    )
    seen = api.view(rid, "abc"[(seat + 1) % 3])
    assert "candidate" not in str(seen)
    assert "game" not in str(seen["controls"])
    assert "hands" not in str(seen["controls"])
    assert "uid" not in str(seen["controls"])
    observer = api.view(rid, "owner-outside", owner=True)
    assert "hand" not in observer
    assert "candidate" not in str(observer)
