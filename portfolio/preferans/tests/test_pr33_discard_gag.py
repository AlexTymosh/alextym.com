"""Server-side privacy and idempotency of the optional presentation."""

from types import SimpleNamespace

import pytest

from preferans.domain.cards import FULL_DECK
from preferans.online import discard_gag
from preferans.online.codec import decode
from preferans.online.store import FirestoreRooms, StoreError
from test_secure_rooms import FakeDB, transactional
from test_realtime_store import setup_realtime  # noqa: F401 - shared pytest fixture


def test_marker_consumed_once_and_no_card_data():
    control = {}
    discard_gag.record_discard(control, "first", 2, 1000, True)
    assert discard_gag.project(control, "first", auction=False) == {
        "hidden_discard": {"seat": 2, "at_ms": 1000}
    }
    assert discard_gag.begin(control, "first", "second", 5000)
    assert discard_gag.project(control, "second", auction=True) == {
        "redeal_gag": {"seat": 2, "at_ms": 5000}
    }
    assert discard_gag.active(control, "second", 5000 + discard_gag.GAG_TOTAL_MS - 1)
    assert not discard_gag.active(control, "second", 5000 + discard_gag.GAG_TOTAL_MS)
    assert not discard_gag.project(control, "second", auction=False)
    assert not discard_gag.begin(control, "second", "third", 20000)
    assert control == {}
    discard_gag.record_discard(control, "third", 0, 20000, False)
    assert control == {}


def setup(monkeypatch):
    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    clock = [1_800_000_000_000]
    api = FirestoreRooms(
        FakeDB(),
        firestore_module=SimpleNamespace(transactional=transactional),
        now_ms=lambda: clock[0],
    )
    rid = api.create("a", "pr33-create")["room_id"]
    api.join(rid, "b", "pr33-join-b", 0)
    api.join(rid, "c", "pr33-join-c", 1)
    api.start(rid, "a", "pr33-start", 2, False)
    return api, rid, clock


def send(api, rid, uid, key, action, args):
    return api.command(rid, uid, key, api.view(rid, uid)["version"], action, args)


@pytest.mark.parametrize("hide", [False, True])
def test_discard_and_next_deal_are_authoritative(monkeypatch, hide):
    api, rid, clock = setup(monkeypatch)
    initial = api.view(rid, "a")
    seat = initial["turn"]
    uid = "abc"[seat]
    send(api, rid, uid, "pr33-bid", "bid", {"bid": {"kind": "misere", "level": None, "suit": None}})
    for i in range(2):
        v = api.view(rid, "a")
        send(api, rid, "abc"[v["turn"]], f"pr33-pass-{i}", "pass", {})
    cards = api.view(rid, uid)["widow"]
    with pytest.raises(StoreError):
        send(api, rid, uid, "pr33-invalid-hide", "discard", {"cards": cards, "hide_under_sheet": 1})
    with pytest.raises(StoreError):
        send(
            api,
            rid,
            "abc"[(seat + 1) % 3],
            "pr33-wrong-discard",
            "discard",
            {"cards": cards, "hide_under_sheet": True},
        )
    send(api, rid, uid, "pr33-discard", "discard", {"cards": cards, "hide_under_sheet": hide})
    for player in "abc":
        v = api.view(rid, player)
        assert ("hidden_discard" in v) == hide
        if hide:
            assert v["hidden_discard"] == {"seat": seat, "at_ms": clock[0]}
        if player != uid:
            assert "own_discard" not in v
    events = api.events(rid, uid)["events"]
    assert next(e["data"] for e in events if e["action"] == "discard") == (
        {"hide_under_sheet": True} if hide else {}
    )
    send(api, rid, uid, "pr33-misere", "misere_offer", {})
    for i, defender in enumerate(player for player in "abc" if player != uid):
        send(api, rid, defender, f"pr33-approve-{i}", "misere_vote", {"approve": True})
    between = api.view(rid, "a")
    assert between["status"] == "between"
    clock[0] += 5000
    started = api.start(rid, "a", "pr33-next-start", between["version"], False)
    assert api.start(rid, "a", "pr33-next-start", between["version"], False) == started
    new = api.view(rid, "a")
    assert new["game_id"] != between["game_id"] and new["dealer"] == (between["dealer"] + 1) % 3
    assert new["score"] == between["score"]
    assert ("redeal_gag" in new) == hide
    assert "hidden_discard" not in new
    for player in "abc":
        v = api.view(rid, player)
        assert len(v["hand"]) == 10 and v["widow"] == []
        if hide:
            assert v["redeal_gag"] == {"seat": seat, "at_ms": clock[0]}
            assert v["server_clock_ms"] == clock[0]
    state = decode(api.db.docs[f"preferans_rooms/{rid}/private/current"]["game"])
    cards_all = [card for hand in state.hands for card in hand] + list(state.widow)
    assert len(cards_all) == 32 and set(cards_all) == set(FULL_DECK)
    next_uid = "abc"[new["turn"]]
    if hide:
        clock[0] += discard_gag.GAG_TOTAL_MS - 1
        with pytest.raises(StoreError) as exc:
            send(api, rid, next_uid, "pr33-early-pass", "pass", {})
        assert exc.value.code == 409
        assert api.view(rid, next_uid)["version"] == new["version"]
        clock[0] += 1
    send(api, rid, next_uid, "pr33-valid-pass", "pass", {})


def test_counter_target_must_match_current_actor(monkeypatch):
    api, rid, _ = setup(monkeypatch)
    view = api.view(rid, "a")
    target = view["turn"]
    initiator = "abc"[(target + 1) % 3]
    for i, uid in enumerate("abc"):
        send(api, rid, uid, f"pr33-pulse-{i}", "pulse", {})
    with pytest.raises(StoreError) as exc:
        send(
            api, rid, initiator, "pr33-counter-wrong", "counter_start", {"target": (target + 2) % 3}
        )
    assert exc.value.code == 422
    with pytest.raises(StoreError):
        send(api, rid, "abc"[target], "pr33-counter-self", "counter_start", {"target": target})
    send(api, rid, initiator, "pr33-counter-correct", "counter_start", {"target": target})
    counter = api.view(rid, initiator)["controls"]["counter"]
    assert counter["target"] == target and counter["initiator"] == (target + 1) % 3


def test_realtime_auto_deal_consumes_hidden_marker(setup_realtime):  # noqa: F811
    api, rid, clock, runtime, tickets, conns = setup_realtime
    initial = api.view(rid, "a")
    seat = initial["turn"]
    uid = "abc"[seat]
    send(
        api,
        rid,
        uid,
        "pr33-rt-bid",
        "bid",
        {"bid": {"kind": "misere", "level": None, "suit": None}},
    )
    for i in range(2):
        view = api.view(rid, "a")
        send(api, rid, "abc"[view["turn"]], f"pr33-rt-pass-{i}", "pass", {})
    send(
        api,
        rid,
        uid,
        "pr33-rt-hide",
        "discard",
        {"cards": api.view(rid, uid)["widow"], "hide_under_sheet": True},
    )
    send(api, rid, uid, "pr33-rt-offer", "misere_offer", {})
    for i, defender in enumerate(player for player in "abc" if player != uid):
        send(api, rid, defender, f"pr33-rt-approve-{i}", "misere_vote", {"approve": True})
    between = api.view(rid, "a")
    assert between["status"] == "between"
    clock[0] = between["next_deal"]["deadline_ms"]
    api.sync_realtime(rid, "a")
    new = api.view(rid, "a")
    assert new["redeal_gag"] == {"seat": seat, "at_ms": clock[0]}
    assert new["score"] == between["score"]
    for ticket, connection in zip(tickets, conns):
        snapshot = runtime.snapshot(ticket, connection, clock[0])
        assert snapshot["redeal_gag"] == new["redeal_gag"]
        assert len(snapshot["hand"]) == 10
    api.sync_realtime(rid, "b")
    assert api.view(rid, "a")["version"] == new["version"]
