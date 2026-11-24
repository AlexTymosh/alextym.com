"""Exercise the actual store with the existing transactional fake Firebase fixture."""

from __future__ import annotations

import pytest

from preferans.online.store import StoreError
from test_realtime_store import setup_realtime  # noqa: F401 - shared pytest fixture


def settle_passout(api, rid):
    for n in range(3):
        view = api.view(rid, "a")
        assert view["phase"] == "auction"
        api.command(rid, "abc"[view["turn"]], f"pass-pr12-{n}", view["version"], "pass", {})
    for n in range(30):
        public = api.view(rid, "a")
        owner = public["turn"]
        uid = "abc"[owner]
        own = api.view(rid, uid)
        api.command(
            rid,
            uid,
            f"play-pr12-{n}",
            own["version"],
            "play",
            {"owner": owner, "card": own["legal_cards"][0]},
        )
    finished = api.view(rid, "a")
    assert finished["status"] == "awaiting_settlement"
    api.settle(
        rid,
        "a",
        "settle-pr12-01",
        finished["version"],
        {"regular_route": "pool", "passout_routes": ["pool", "pool", "pool"]},
        False,
    )
    between = api.view(rid, "a")
    assert between["status"] == "between"
    return between


def test_next_deal_exact_boundary_and_duplicate_sync(setup_realtime):  # noqa: F811
    api, rid, clock, runtime, tickets, conns = setup_realtime
    between = settle_passout(api, rid)
    old_game = between["game_id"]
    assert between["next_deal"]["after_game_id"] == old_game
    assert between["next_deal"]["deadline_ms"] == clock[0] + 5_000
    with pytest.raises(StoreError) as exc:
        api.start(rid, "a", "early-start-pr12", between["version"], False)
    assert exc.value.code == 409
    clock[0] += 4_999
    api.sync_realtime(rid, "a")
    assert api.view(rid, "a")["game_id"] == old_game
    clock[0] += 1
    api.sync_realtime(rid, "a")
    new = api.view(rid, "a")
    assert new["status"] == "playing" and new["phase"] == "auction"
    assert new["game_id"] != old_game
    assert "next_deal" not in new
    assert new["dealer"] == (between["dealer"] + 1) % 3
    api.sync_realtime(rid, "b")
    assert api.view(rid, "a")["version"] == new["version"]
    assert api.view(rid, "a")["game_id"] == new["game_id"]
    for uid in "abc":
        view = api.view(rid, uid)
        assert len(view["hand"]) == 10 and view["widow"] == []
        assert view["score"] == between["score"]


def test_next_deal_waits_for_disconnected_player(setup_realtime):  # noqa: F811
    api, rid, clock, runtime, tickets, conns = setup_realtime
    between = settle_passout(api, rid)
    clock[0] += 1_000
    runtime.disconnect(tickets[1], conns[1], clock[0])
    api.sync_realtime(rid, "a")
    frozen = api.view(rid, "a")
    assert frozen["next_deal"]["deadline_ms"] is None
    assert frozen["controls"]["paused"]
    clock[0] += 6_000
    api.sync_realtime(rid, "a")
    assert api.view(rid, "a")["game_id"] == between["game_id"]
    runtime.connect(tickets[1], api.view(rid, "b"), clock[0])
    api.sync_realtime(rid, "a")
    resumed = api.view(rid, "a")
    assert not resumed["controls"]["paused"]
    assert resumed["next_deal"]["deadline_ms"] >= clock[0]
    clock[0] = resumed["next_deal"]["deadline_ms"]
    api.sync_realtime(rid, "a")
    assert api.view(rid, "a")["game_id"] != between["game_id"]
