from dataclasses import replace
from types import SimpleNamespace

import pytest

from preferans.online.codec import decode, encode
from preferans.online.store import FirestoreRooms, StoreError
from test_secure_rooms import FakeDB, transactional


def setup(monkeypatch):
    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    api = FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))
    rid = api.create("a", "pr24-create")["room_id"]
    api.join(rid, "b", "pr24-join-b", 0)
    api.join(rid, "c", "pr24-join-c", 1)
    api.start(rid, "a", "pr24-start", 2, False)
    for i in range(3):
        view = api.view(rid, "a")
        api.command(rid, "abc"[view["turn"]], f"pr24-pass-{i}", view["version"], "pass", {})
    return api, rid


def command(api, rid, uid, key, action, args):
    return api.command(rid, uid, key, api.view(rid, uid)["version"], action, args)


def test_two_seat_choices_cannot_be_bypassed_or_spoofed(monkeypatch):
    api, rid = setup(monkeypatch)
    record = api.db.docs[f"preferans_rooms/{rid}/private/current"]
    record["score"] = encode(replace(decode(record["score"]), pool=(20, 10, 8), hill=(2, 5, 0)))
    command(api, rid, "c", "pr24-offer-c", "claim_offer", {})
    with pytest.raises(StoreError):
        command(api, rid, "a", "pr24-counter-block", "counter_start", {})
    command(api, rid, "a", "pr24-vote-a", "claim_vote", {"approve": True})
    before = api.view(rid, "b")
    accepted = api.command(
        rid, "b", "pr24-vote-b", before["version"], "claim_vote", {"approve": True}
    )
    assert (
        api.command(rid, "b", "pr24-vote-b", before["version"], "claim_vote", {"approve": True})
        == accepted
    )
    finished = api.view(rid, "a")
    assert finished["status"] == "awaiting_settlement"
    assert finished["played_tricks"] == 0 and finished["tricks_won"] == [0, 0, 10]
    assert finished["last_trick"] == []
    assert finished["settlement_options"]["passout_pending"] == [1]
    with pytest.raises(StoreError) as denied:
        api.settle(
            rid,
            "a",
            "pr24-premature",
            finished["version"],
            {"regular_route": "pool", "passout_routes": ["pool"] * 3},
            False,
        )
    assert denied.value.code == 409
    with pytest.raises(StoreError):
        command(api, rid, "a", "pr24-spoof", "passout_reward", {"route": "pool", "seat": 1})
    command(api, rid, "b", "pr24-reward-b", "passout_reward", {"route": "pool"})
    assert api.view(rid, "a")["settlement_options"]["passout_pending"] == [0]
    command(api, rid, "a", "pr24-reward-a", "passout_reward", {"route": "help"})
    final = api.view(rid, "a")
    assert final["settlement_options"]["passout_pending"] == []
    assert final["settlement_options"]["passout_defaults"] == ["help", "pool", "pool"]
    with pytest.raises(StoreError) as wrong:
        api.settle(
            rid,
            "a",
            "pr24-wrong-route",
            final["version"],
            {"regular_route": "pool", "passout_routes": ["hill_first", "pool", "pool"]},
            False,
        )
    assert wrong.value.code == 422
    api.settle(
        rid,
        "a",
        "pr24-settle",
        final["version"],
        {"regular_route": "pool", "passout_routes": ["help", "pool", "pool"]},
        False,
    )
    after = api.view(rid, "a")
    assert after["status"] == "between"
    assert after["score"]["pool"] == [20, 12, 8]
    assert after["score"]["hill"] == [2, 5, 10]
    assert after["score"]["vists"][0][1] == 10
    events = api.events(rid, "a")["events"]
    assert all(
        "cards" not in event["data"]
        for event in events
        if event["action"] in {"claim_offer", "claim_vote"}
    )
