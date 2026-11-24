"""Transactional shared-room integration using the existing Firestore fake."""

import copy

import pytest

from preferans.online.store import StoreError
from test_auto_deal_store import settle_passout
from test_realtime_store import setup_realtime  # noqa: F401


def shared(api, rid, uid, action, **args):
    view = api.view(rid, uid)
    return api.command(
        rid,
        uid,
        f"shared-{view['version']}-{uid}-{action}",
        view["version"],
        action,
        {"presentation_version": view["presentation"]["revision"], **args},
    )


def test_shared_overlay_replacement_and_duplicate_requests(setup_realtime):  # noqa: F811
    api, rid, clock, runtime, tickets, conns = setup_realtime
    v = api.view(rid, "a")
    args = {"presentation_version": v["presentation"]["revision"], "kind": "score_sheet"}
    response = api.command(rid, "a", "shared-open-score", v["version"], "overlay_open", args)
    before = copy.deepcopy(api.db.docs)
    assert (
        api.command(rid, "a", "shared-open-score", v["version"], "overlay_open", args) == response
    )
    assert api.db.docs == before
    for uid in "abc":
        assert api.view(rid, uid)["presentation"]["overlay"]["kind"] == "score_sheet"
    with pytest.raises(StoreError) as exc:
        api.command(rid, "b", "shared-stale-open", v["version"], "overlay_open", args)
    assert exc.value.code == 409
    assert api.db.docs == before
    shared(api, rid, "b", "overlay_open", kind="radio")
    shared(api, rid, "c", "break_start")
    overlay = api.view(rid, "a")["presentation"]["overlay"]
    shared(api, rid, "c", "overlay_close", overlay_id=overlay["id"])
    v = api.view(rid, "a")
    assert v["controls"]["pause_reasons"] == ["break"]
    bid = v["presentation"]["break"]["id"]
    for uid in "ab":
        shared(api, rid, uid, "break_ready", break_id=bid, ready=True)
    assert api.view(rid, "a")["controls"]["paused"]
    shared(api, rid, "c", "break_ready", break_id=bid, ready=True)
    assert not api.view(rid, "a")["controls"]["paused"]


def test_nonmember_and_invalid_widow_denied(setup_realtime):  # noqa: F811
    api, rid, *_ = setup_realtime
    v = api.view(rid, "a")
    args = {"presentation_version": 0, "kind": "widow_replay"}
    with pytest.raises(StoreError):
        api.command(rid, "outsider", "outsider-open", v["version"], "overlay_open", args)
    with pytest.raises(StoreError) as exc:
        api.command(rid, "a", "hidden-widow-open", v["version"], "overlay_open", args)
    assert exc.value.code == 409
    assert api.view(rid, "a")["presentation"]["overlay"] is None


def test_replay_closes_only_after_valid_card(setup_realtime):  # noqa: F811
    api, rid, *_ = setup_realtime
    for n in range(3):
        v = api.view(rid, "a")
        api.command(rid, "abc"[v["turn"]], f"replay-pass-{n}", v["version"], "pass", {})
    for n in range(3):
        v = api.view(rid, "a")
        uid = "abc"[v["controller"]]
        own = api.view(rid, uid)
        api.command(
            rid,
            uid,
            f"replay-card-{n}",
            own["version"],
            "play",
            {"owner": own["turn"], "card": own["legal_cards"][0]},
        )
    shared(api, rid, "b", "overlay_open", kind="last_trick")
    v = api.view(rid, "a")
    uid = "abc"[v["controller"]]
    own = api.view(rid, uid)
    before = copy.deepcopy(api.db.docs)
    with pytest.raises(StoreError):
        api.command(
            rid,
            uid,
            "replay-invalid-card",
            own["version"],
            "play",
            {"owner": own["turn"], "card": {"rank": 2, "suit": "S"}},
        )
    assert api.db.docs == before
    api.command(
        rid,
        uid,
        "replay-valid-card",
        own["version"],
        "play",
        {"owner": own["turn"], "card": own["legal_cards"][0]},
    )
    after = api.view(rid, "a")
    assert not after["controls"]["paused"]
    assert after["presentation"]["overlay"] is None
    assert len(after["trick"]) == 1


def test_break_freezes_next_deal_and_disconnect_resets_votes(setup_realtime):  # noqa: F811
    api, rid, clock, runtime, tickets, conns = setup_realtime
    v = settle_passout(api, rid)
    clock[0] += 1000
    shared(api, rid, "a", "break_start")
    paused = api.view(rid, "a")
    assert paused["next_deal"]["remaining_ms"] == 4000
    bid = paused["presentation"]["break"]["id"]
    shared(api, rid, "b", "break_ready", break_id=bid, ready=True)
    runtime.disconnect(tickets[1], conns[1], clock[0])
    api.sync_realtime(rid, "a")
    assert not api.view(rid, "a")["presentation"]["break"]["ready"][1]
    clock[0] += 6000
    api.sync_realtime(rid, "a")
    assert api.view(rid, "a")["game_id"] == v["game_id"]
    runtime.connect(tickets[1], api.view(rid, "b"), clock[0])
    api.sync_realtime(rid, "a")
    for uid in "abc":
        shared(api, rid, uid, "break_ready", break_id=bid, ready=True)
    resumed = api.view(rid, "a")
    assert resumed["next_deal"]["deadline_ms"] == clock[0] + 4000
    clock[0] += 4000
    api.sync_realtime(rid, "a")
    assert api.view(rid, "a")["game_id"] != v["game_id"]
