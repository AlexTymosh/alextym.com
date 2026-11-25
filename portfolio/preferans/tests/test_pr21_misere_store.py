from types import SimpleNamespace

import pytest

from preferans.online.store import FirestoreRooms, StoreError
from test_secure_rooms import FakeDB, transactional


def test_misere_offer_transaction_settles_once_without_admin(monkeypatch):
    monkeypatch.delenv("PREFERANS_REALTIME_ENABLED", raising=False)
    api = FirestoreRooms(FakeDB(), firestore_module=SimpleNamespace(transactional=transactional))
    rid = api.create("a", "pr21-create")["room_id"]
    api.join(rid, "b", "pr21-join-b", 0)
    api.join(rid, "c", "pr21-join-c", 1)
    api.start(rid, "a", "pr21-start", 2, False)
    initial = api.view(rid, "a")
    declarer = initial["turn"]
    # A real auction: the first actor announces misere, both others pass.
    api.command(
        rid,
        "abc"[declarer],
        "pr21-bid",
        initial["version"],
        "bid",
        {
            "bid": {"kind": "misere", "level": None, "suit": None},
        },
    )
    for i in range(2):
        view = api.view(rid, "a")
        api.command(rid, "abc"[view["turn"]], f"pr21-pass-{i}", view["version"], "pass", {})
    uid = "abc"[declarer]
    own = api.view(rid, uid)
    api.command(rid, uid, "pr21-discard", own["version"], "discard", {"cards": own["widow"]})
    own = api.view(rid, uid)
    api.command(rid, uid, "pr21-offer", own["version"], "misere_offer", {})
    defenders = [player for player in "abc" if player != uid]
    # Choose a non-admin for the decisive confirmation when possible.
    defenders.sort(key=lambda player: player != "a")
    v = api.view(rid, defenders[0])
    assert v["misere_offer"]["can_vote"] and len(v["open_hands"][0]["cards"]) == 10
    first = api.command(
        rid, defenders[0], "pr21-vote-first", v["version"], "misere_vote", {"approve": True}
    )
    assert api.view(rid, defenders[1])["score"]["pool"] == [0, 0, 0]
    with pytest.raises(StoreError) as stale:
        api.command(
            rid, defenders[1], "pr21-vote-stale", v["version"], "misere_vote", {"approve": True}
        )
    assert stale.value.code == 409
    approved = api.command(
        rid, defenders[1], "pr21-vote-second", first["version"], "misere_vote", {"approve": True}
    )
    assert approved["status"] == "between"
    assert (
        api.command(
            rid,
            defenders[1],
            "pr21-vote-second",
            first["version"],
            "misere_vote",
            {"approve": True},
        )
        == approved
    )
    settled = api.view(rid, uid)
    assert settled["score"]["pool"][declarer] == 10
    assert sum(settled["score"]["pool"]) == 10
    assert settled["end_reason"] == "misere_accepted"
    assert "misere_offer" not in settled and not settled["open_hands"]
    events = api.events(rid, defenders[0])["events"]
    assert all(
        "cards" not in e["data"] for e in events if e["action"] in {"misere_offer", "misere_vote"}
    )
