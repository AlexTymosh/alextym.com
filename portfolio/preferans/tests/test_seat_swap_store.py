"""Real room service and transaction fixture; no production calls."""

import copy
from types import SimpleNamespace

import pytest

from preferans.online import store
from preferans.online.realtime import RealtimeHub, Ticket
from test_secure_rooms import FakeDB, FakeTransaction, transactional


@pytest.fixture
def lobby(monkeypatch):
    for key in (
        "PORTFOLIO_LAB_ENABLED",
        "PREFERANS_ROOMS_ENABLED",
        "PREFERANS_REALTIME_ENABLED",
        "PREFERANS_REALTIME_SINGLE_WORKER",
    ):
        monkeypatch.setenv(key, "true")
    hub = RealtimeHub()
    monkeypatch.setattr(store, "hub", hub)
    now = 1_800_000_000_000
    api = store.FirestoreRooms(
        FakeDB(), firestore_module=SimpleNamespace(transactional=transactional), now_ms=lambda: now
    )
    rid = api.create("a", "create-swap-01", require_ready=True)["room_id"]
    api.join(rid, "b", "join-swap-b", 0)
    api.join(rid, "c", "join-swap-c", 1)
    pairs = []
    for seat, uid in enumerate("abc"):
        ticket = Ticket(rid, uid, seat, "https://example.test", "credential", now + 30_000)
        pairs.append((ticket, hub.connect(ticket, api.view(rid, uid), now)))
    return api, rid, hub, now, pairs


def command(api, rid, uid, action, args, key):
    return api.command(rid, uid, key, api.view(rid, uid)["version"], action, args)


def propose(api, rid):
    command(api, rid, "a", "seat_swap_offer", {"to": 2}, "offer-swap-01")
    return api.view(rid, "a")["seat_swap"]["id"]


def test_swap_store_consent_revoke_and_deal(lobby):
    api, rid, hub, now, pairs = lobby
    for uid in "abc":
        command(api, rid, uid, "lobby_ready", {"ready": True}, f"ready-swap-{uid}")
    offer = propose(api, rid)
    with pytest.raises(store.StoreError) as exc:
        api.start(rid, "a", "start-too-soon", api.view(rid, "a")["version"], False)
    assert exc.value.code == 409
    with pytest.raises(store.StoreError):
        api.command(
            rid,
            "unknown",
            "outsider-swap",
            api.view(rid, "a")["version"],
            "seat_swap_vote",
            {"id": offer, "approve": True},
        )
    args = {"id": offer, "approve": True}
    command(api, rid, "b", "seat_swap_vote", args, "vote-swap-b")
    assert api.view(rid, "a")["my_seat"] == 0
    v = api.view(rid, "c")["version"]
    result = api.command(rid, "c", "vote-swap-c", v, "seat_swap_vote", args)
    before = copy.deepcopy(api.db.docs)
    assert api.command(rid, "c", "vote-swap-c", v, "seat_swap_vote", args) == result
    assert api.db.docs == before
    for uid, seat in zip("abc", (2, 1, 0)):
        view = api.view(rid, uid)
        assert view["my_seat"] == seat and view["seat_revision"] == 1
        assert view["lobby_setup"]["ready"] == [False] * 3
        assert view["lobby_setup"]["dealer"] == 0
        assert "seat_swap" not in view and "hand" not in view
    for ticket, conn in pairs:
        assert not hub.current(ticket, conn, now)
    for uid in "abc":
        view = api.view(rid, uid)
        ticket = Ticket(
            rid, uid, view["my_seat"], "https://example.test", "credential", now + 30_000
        )
        hub.connect(ticket, view, now)
        command(api, rid, uid, "lobby_ready", {"ready": True}, f"ready-again-{uid}")
    api.start(rid, "a", "start-after-swap", api.view(rid, "a")["version"], False)
    hands = [api.view(rid, uid) for uid in "abc"]
    assert [v["my_seat"] for v in hands] == [2, 1, 0]
    assert all(len(v["hand"]) == 10 and v["widow"] == [] for v in hands)
    assert len({str(card) for view in hands for card in view["hand"]}) == 30
    assert all(v["dealer"] == 0 for v in hands)


def test_failed_transaction_does_not_revoke_connections(lobby, monkeypatch):
    api, rid, hub, now, pairs = lobby
    offer = propose(api, rid)
    args = {"id": offer, "approve": True}
    command(api, rid, "b", "seat_swap_vote", args, "vote-swap-b")
    before = copy.deepcopy(api.db.docs)

    def fail(_self):
        raise RuntimeError("Simulated failure")

    monkeypatch.setattr(FakeTransaction, "commit", fail)
    with pytest.raises(RuntimeError, match="Simulated failure"):
        command(api, rid, "c", "seat_swap_vote", args, "vote-swap-c")
    assert api.db.docs == before
    assert all(hub.current(ticket, conn, now) for ticket, conn in pairs)


def test_redeemed_stale_seat_ticket_is_recoverable_not_access_denial(lobby, monkeypatch):
    from preferans.online import realtime_api
    from preferans.online.realtime import HubError

    api, rid, hub, _, pairs = lobby
    monkeypatch.setattr(realtime_api, "hub", hub)
    monkeypatch.setattr(realtime_api, "_store", lambda: api)
    monkeypatch.setattr(realtime_api, "origin_allowed", lambda _: True)
    offer = propose(api, rid)
    args = {"id": offer, "approve": True}
    command(api, rid, "b", "seat_swap_vote", args, "vote-swap-b")
    command(api, rid, "c", "seat_swap_vote", args, "vote-swap-c")
    old_ticket = pairs[0][0]
    with pytest.raises(HubError, match="Seat changed"):
        realtime_api._verified_view(old_ticket, lambda _: ("a", False))
    # A fresh ticket from the authenticated current seat can connect.
    new_ticket = Ticket(rid, "a", 2, old_ticket.origin, "credential", old_ticket.expires)
    _, view = realtime_api._verified_view(new_ticket, lambda _: ("a", False))
    assert view["my_seat"] == 2
