"""Single-process, bounded Preferans delivery hub. No Firebase writes here.

Only verified seat projections enter this module. All authoritative mutations
remain in Firestore. The process lock orders local commit and presence changes;
it is not a distributed lock. Enable only on a verified single worker/instance.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .live_relay import LiveRelay
from .publish_signal import PublishSignal

PROTOCOL = 1
TICKET_MS = 30_000
WS_LEASE_MS = 35_000
HTTP_LEASE_MS = 100_000
AUTH_MS = 60_000
CHECKPOINT_MS = 60_000
MAX_ROOMS = 16
MAX_TICKETS = 128
ROOM_IDLE_MS = 10 * 60_000


def now_ms() -> int:
    return int(time.time() * 1000)


def enabled() -> bool:
    return all(
        os.getenv(key) == "true"
        for key in (
            "PORTFOLIO_LAB_ENABLED",
            "PREFERANS_ROOMS_ENABLED",
            "PREFERANS_REALTIME_ENABLED",
            "PREFERANS_REALTIME_SINGLE_WORKER",
        )
    )


def origin_allowed(origin: str) -> bool:
    # Explicit exact browser origins; no wildcard, no path, no forwarded host trust.
    configured = {
        v.strip().rstrip("/")
        for v in os.getenv("PREFERANS_REALTIME_ORIGINS", "").split(",")
        if v.strip()
    }
    return (
        bool(origin)
        and origin in configured
        and origin.startswith(("https://", "http://localhost:", "http://127.0.0.1:"))
    )


class HubError(Exception):
    pass


@dataclass(frozen=True, repr=False)
class Ticket:
    room: str
    uid: str
    seat: int
    origin: str
    authorization: str
    expires: int


@dataclass
class Lease:
    uid: str
    connection: str | None
    seen: int
    lost_at: int | None = None

    def live(self, at: int) -> bool:
        return self.lost_at is None and 0 <= at - self.seen <= (
            WS_LEASE_MS if self.connection else HTTP_LEASE_MS
        )

    def lost(self, at: int) -> int:
        return (
            self.lost_at
            if self.lost_at is not None
            else min(at, self.seen + (WS_LEASE_MS if self.connection else HTTP_LEASE_MS))
        )


@dataclass
class Room:
    touched: int
    leases: dict[int, Lease] = field(default_factory=dict)
    views: dict[str, dict[str, Any]] = field(default_factory=dict)
    revision: int = -1
    last_sync: int = 0
    signature: tuple[bool, ...] | None = None
    syncing: bool = False
    retry_sync_at: int = 0
    loss_generation: int = 0
    handled_generation: int = 0
    live_media: LiveRelay = field(default_factory=LiveRelay)


class RealtimeHub:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.commit_lock = threading.RLock()
        self.publish_signal = PublishSignal()
        self.pending_handshakes = 0
        self.epoch = secrets.token_hex(16)
        self.rooms: dict[str, Room] = {}
        self.tickets: dict[str, Ticket] = {}
        # Process-local estimates, deliberately no per-heartbeat database metrics.
        self.metrics: dict[str, int] = {
            "tickets": 0,
            "connections": 0,
            "heartbeats": 0,
            "published": 0,
            "sync_reads": 0,
            "sync_writes": 0,
            "sync_failures": 0,
            "snapshots_sent": 0,
            "mutation_commits": 0,
            "mutation_min_reads": 0,
            "mutation_min_writes": 0,
        }

    def reserve_handshake(self) -> bool:
        with self.lock:
            if self.pending_handshakes >= 16:
                return False
            self.pending_handshakes += 1
            return True

    def release_handshake(self) -> None:
        with self.lock:
            self.pending_handshakes = max(0, self.pending_handshakes - 1)

    def _prune(self, at: int) -> None:
        for key in [k for k, t in self.tickets.items() if t.expires <= at]:
            del self.tickets[key]
        for key in [
            k
            for k, r in self.rooms.items()
            if at - r.touched > ROOM_IDLE_MS
            and not r.syncing
            and not any(v.live(at) for v in r.leases.values())
        ]:
            del self.rooms[key]

    def _room(self, room: str, at: int) -> Room:
        self._prune(at)
        if room not in self.rooms:
            if len(self.rooms) >= MAX_ROOMS:
                raise HubError("Room capacity reached")
            self.rooms[room] = Room(at)
        r = self.rooms[room]
        r.touched = at
        return r

    def issue(
        self, room: str, uid: str, seat: int, origin: str, authorization: str, at: int
    ) -> str:
        if seat not in (0, 1, 2) or not origin_allowed(origin) or not authorization:
            raise HubError("Ticket denied")
        with self.lock:
            self._prune(at)
            if len(self.tickets) >= MAX_TICKETS:
                raise HubError("Ticket capacity reached")
            # One outstanding ticket for the same room/identity.
            for key in [k for k, t in self.tickets.items() if t.room == room and t.uid == uid]:
                del self.tickets[key]
            token = secrets.token_urlsafe(32)
            self.tickets[token] = Ticket(room, uid, seat, origin, authorization, at + TICKET_MS)
            self.metrics["tickets"] += 1
            return token

    def redeem(self, token: str, room: str, origin: str, at: int) -> Ticket:
        with self.lock:
            self._prune(at)
            ticket = self.tickets.pop(token, None)
            if (
                ticket is None
                or ticket.expires <= at
                or ticket.room != room
                or ticket.origin != origin
            ):
                raise HubError("Ticket denied")
            return ticket

    def connect(self, ticket: Ticket, view: dict, at: int) -> str:
        if view.get("room_id") != ticket.room or view.get("my_seat") != ticket.seat:
            raise HubError("Seat denied")
        with self.lock:
            r = self._room(ticket.room, at)
            connection = secrets.token_hex(16)
            old = r.leases.get(ticket.seat)
            if old and not old.live(at):
                r.loss_generation += 1
            r.leases[ticket.seat] = Lease(ticket.uid, connection, at)
            self._accept_view(r, ticket.uid, view)
            self.metrics["connections"] += 1
            return connection

    def _accept_view(self, room: Room, uid: str, view: dict) -> None:
        if view.get("my_seat") not in (0, 1, 2):
            return
        version = view["version"]
        if version < room.revision:
            return
        if version > room.revision:
            room.views.clear()
            room.revision = version
        room.views[uid] = view

    def invalidate_seats(self, room: str, at: int) -> None:
        """After a committed lobby permutation, revoke every old seat binding."""
        with self.lock:
            for key in [k for k, t in self.tickets.items() if t.room == room]:
                del self.tickets[key]
            r = self.rooms.get(room)
            if r is not None:
                r.leases.clear()
                r.views.clear()
                r.live_media = LiveRelay()
                r.loss_generation += 1
                r.signature = None
                r.touched = at

    def publish(self, room: str, views: dict[str, dict], at: int) -> None:
        with self.lock:
            r = self.rooms.get(room)
            if r is None:
                return
            if not views:
                return
            version = next(iter(views.values()))["version"]
            if version < r.revision:
                return
            if any(view.get("status") == "archived" for view in views.values()):
                r.live_media = LiveRelay()
            r.views = {uid: view for uid, view in views.items() if view.get("my_seat") in (0, 1, 2)}
            r.revision = version
            r.touched = at
            self.metrics["published"] += 1
        self.publish_signal.notify(room)

    def fallback(self, room: str, uid: str, view: dict, at: int) -> None:
        seat = view.get("my_seat")
        if seat not in (0, 1, 2) or view.get("room_id") != room:
            raise HubError("Seat denied")
        with self.lock:
            r = self._room(room, at)
            current = r.leases.get(seat)
            if not (current and current.uid == uid and current.connection and current.live(at)):
                if current and not current.live(at):
                    r.loss_generation += 1
                r.leases[seat] = Lease(uid, None, at)
            self._accept_view(r, uid, view)
            self.metrics["heartbeats"] += 1

    def current(self, ticket: Ticket, connection: str, at: int) -> bool:
        with self.lock:
            r = self.rooms.get(ticket.room)
            lease = r.leases.get(ticket.seat) if r else None
            return bool(
                lease
                and lease.uid == ticket.uid
                and lease.connection == connection
                and lease.live(at)
            )

    def heartbeat(self, ticket: Ticket, connection: str, at: int) -> None:
        with self.lock:
            if not self.current(ticket, connection, at):
                raise HubError("Connection expired")
            r = self.rooms[ticket.room]
            r.leases[ticket.seat].seen = r.touched = at
            self.metrics["heartbeats"] += 1

    def disconnect(self, ticket: Ticket, connection: str, at: int) -> None:
        with self.lock:
            r = self.rooms.get(ticket.room)
            lease = r.leases.get(ticket.seat) if r else None
            if (
                lease
                and lease.uid == ticket.uid
                and lease.connection == connection
                and lease.lost_at is None
            ):
                lease.lost_at = at
                r.loss_generation += 1
                r.touched = at
                # Do not leave an old private snapshot available to another identity.
                r.views.pop(ticket.uid, None)

    def generation(self, room: str) -> tuple[int, bool]:
        with self.lock:
            r = self.rooms.get(room)
            return (
                (r.loss_generation, r.loss_generation > r.handled_generation) if r else (0, False)
            )

    def handled(self, room: str, generation: int) -> None:
        with self.lock:
            r = self.rooms.get(room)
            if r:
                r.handled_generation = max(r.handled_generation, generation)

    def presence(self, room: str, seats: list, at: int) -> list[int | None]:
        with self.lock:
            r = self.rooms.get(room)
            result = []
            for i, uid in enumerate(seats):
                lease = r.leases.get(i) if r else None
                result.append(
                    lease.seen if uid and lease and lease.uid == uid and lease.live(at) else None
                )
            return result

    def statuses(self, room: str, at: int) -> list[str]:
        with self.lock:
            r = self.rooms.get(room)
            result = []
            for i in range(3):
                lease = r.leases.get(i) if r else None
                result.append(
                    "online"
                    if lease and lease.live(at)
                    else "reconnecting"
                    if lease and at - lease.lost(at) < 60_000
                    else "offline"
                )
            return result

    def snapshot(self, ticket: Ticket, connection: str, at: int) -> dict | None:
        with self.lock:
            if not self.current(ticket, connection, at):
                raise HubError("Connection expired")
            view = self.rooms[ticket.room].views.get(ticket.uid)
            if view and view.get("my_seat") == ticket.seat:
                return view
            return None

    def due(self, room: str, at: int, *, claim: bool = True) -> bool:
        """Coalesce reconciliation; quiet healthy rooms do not read Firestore."""
        with self.lock:
            r = self.rooms.get(room)
            if not r or r.syncing or at < r.retry_sync_at:
                return False
            signature = tuple(s == "online" for s in self.statuses(room, at))
            view = next(iter(r.views.values()), {})
            controls = view.get("controls") or {}
            counter = controls.get("counter") or {}
            undo = controls.get("undo") or {}
            deadlines = [
                d
                for d in (counter.get("deadline_ms"), undo.get("deadline_ms"))
                if isinstance(d, int)
            ]
            active = view.get("status") == "playing"
            next_deal = view.get("next_deal") or {}
            next_deadline = next_deal.get("deadline_ms")
            deal_due = (
                view.get("status") == "between"
                and all(signature)
                and not controls.get("paused")
                and not undo
                and type(next_deadline) is int
                and next_deadline <= at
            )
            if (
                deal_due
                or r.signature != signature
                or r.loss_generation > r.handled_generation
                or (
                    active
                    and (
                        any(d <= at for d in deadlines)
                        or (deadlines and at - r.last_sync >= CHECKPOINT_MS)
                    )
                )
            ):
                if claim:
                    r.syncing = True
                return True
            return False

    def synced(
        self, room: str, at: int, success: bool, signature: tuple[bool, ...] | None = None
    ) -> None:
        with self.lock:
            r = self.rooms.get(room)
            if r:
                r.syncing = False
                if success:
                    r.signature = signature
                    r.last_sync = at
                    r.retry_sync_at = 0
                else:
                    r.retry_sync_at = at + 5_000
                    self.metrics["sync_failures"] += 1


hub = RealtimeHub()
