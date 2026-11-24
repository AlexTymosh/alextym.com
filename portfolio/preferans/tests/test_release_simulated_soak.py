"""Fast simulated clock (not a real-duration soak and not a Firestore measurement)."""

from __future__ import annotations

import pytest

from preferans.online.realtime import RealtimeHub, Ticket


@pytest.mark.parametrize("hours", [6, 8])
def test_simulated_three_seat_delivery_and_reconnect(hours):
    hub = RealtimeHub()
    room = "a" * 32
    start = 1_800_000_000_000
    uids = ["synthetic-a", "synthetic-b", "synthetic-c"]
    tickets = [
        Ticket(room, uid, seat, "https://example.test", "synthetic", start + 30_000)
        for seat, uid in enumerate(uids)
    ]

    def views(version):
        return {
            uid: {
                "room_id": room,
                "my_seat": seat,
                "version": version,
                "status": "playing",
                "controls": {},
                "hand": [f"private-{seat}"],
            }
            for seat, uid in enumerate(uids)
        }

    initial = views(0)
    connections = [hub.connect(ticket, initial[ticket.uid], start) for ticket in tickets]
    hub.synced(room, start, True, (True, True, True))
    count = hours * 240
    syncs = 0
    for tick in range(1, count + 1):
        at = start + tick * 15_000
        for ticket, conn in zip(tickets, connections):
            hub.heartbeat(ticket, conn, at)
        # Representative synthetic snapshot every 15s, not an actual game mutation.
        current = views(tick)
        hub.publish(room, current, at)
        assert not hub.due(room, at, claim=False)
        if tick % 240 == 0:
            i = (tick // 240) % 3
            old = connections[i]
            hub.disconnect(tickets[i], old, at)
            assert not hub.current(tickets[i], old, at)
            assert hub.due(room, at)
            signature = tuple(s == "online" for s in hub.statuses(room, at))
            hub.handled(room, hub.generation(room)[0])
            hub.synced(room, at, True, signature)
            syncs += 1
            connections[i] = hub.connect(tickets[i], current[uids[i]], at)
            assert hub.due(room, at)
            hub.handled(room, hub.generation(room)[0])
            hub.synced(room, at, True, (True, True, True))
            syncs += 1
        for seat, (ticket, conn) in enumerate(zip(tickets, connections)):
            snapshot = hub.snapshot(ticket, conn, at)
            assert snapshot["version"] == tick
            assert snapshot["hand"] == [f"private-{seat}"]
        assert len(hub.rooms) == 1 and len(hub.rooms[room].views) == 3
    assert hub.metrics["heartbeats"] == count * 3
    assert hub.metrics["published"] == count
    assert syncs == hours * 2
    assert hub.metrics["sync_reads"] == hub.metrics["sync_writes"] == 0
