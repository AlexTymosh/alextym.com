"""Pure deadline/pause tests; no Firebase, browser or actual users."""

from preferans.online.deal_flow import NEXT_DEAL_MS, due, projection, schedule
from preferans.online.pause_clock import synchronize, transition
from preferans.online.realtime import RealtimeHub


def control(at=100_000):
    return {"presence": [at] * 3, "paused_at": None, "rt_epoch": "boot", "rt_checkpoint_ms": at}


def test_deadline_identity_and_exact_boundary():
    c = control()
    schedule(c, "settled", 100_000)
    assert NEXT_DEAL_MS == 5_000
    assert not due(c, "settled", 104_999)
    assert due(c, "settled", 105_000)
    assert not due(c, "new-game", 105_000)
    assert projection(c, "new-game") is None
    assert projection(c, "settled") == {
        "after_game_id": "settled",
        "deadline_ms": 105_000,
        "remaining_ms": None,
    }
    c["presence"][2] = None
    assert not due(c, "settled", 105_000)


def test_pause_reasons_do_not_erase_one_another():
    c = control()
    schedule(c, "settled", 100_000)
    assert transition(c, {"break"}, 102_000)
    assert projection(c, "settled")["remaining_ms"] == 3_000
    assert transition(c, {"break", "connection_lost"}, 103_000)
    assert transition(c, {"break"}, 120_000)
    assert not due(c, "settled", 130_000)
    assert transition(c, set(), 130_000)
    assert not due(c, "settled", 132_999)
    assert due(c, "settled", 133_000)


def test_restart_never_consumes_unknown_downtime():
    c = control()
    schedule(c, "settled", 100_000)
    synchronize(c, [200_000, None, None], "new-boot", 200_000)
    assert c["next_deal"]["deadline_ms"] is None
    assert c["next_deal"]["remaining_ms"] == 5_000
    synchronize(c, [201_000] * 3, "new-boot", 201_000)
    assert not due(c, "settled", 205_999)
    assert due(c, "settled", 206_000)


def test_pending_vote_or_paused_clock_cannot_deal():
    c = control()
    c["paused_at"] = 100_000
    schedule(c, "settled", 100_000)
    assert not due(c, "settled", 999_999)
    assert projection(c, "settled")["remaining_ms"] == 5_000
    c = control()
    c["vote"] = {"deadline_ms": 200_000}
    schedule(c, "settled", 100_000)
    assert not due(c, "settled", 999_999)


def test_hub_deadline_coalesces_scheduler_without_extra_heartbeat_writes():
    hub = RealtimeHub()
    rid = "a" * 32
    at = 100_000
    for i, uid in enumerate("abc"):
        hub.fallback(
            rid,
            uid,
            {
                "room_id": rid,
                "my_seat": i,
                "version": 1,
                "status": "between",
                "controls": {},
                "next_deal": {"deadline_ms": at + 5_000},
            },
            at,
        )
    hub.synced(rid, at, True, (True, True, True))
    assert not hub.due(rid, at + 4_999)
    assert hub.due(rid, at + 5_000)
    assert not hub.due(rid, at + 5_000)
