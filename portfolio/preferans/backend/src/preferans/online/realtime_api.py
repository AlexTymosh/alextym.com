"""Dedicated WSS entry; host supplies the existing admission/grant verifier."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from .realtime import AUTH_MS, PROTOCOL, HubError, Ticket, enabled, hub, now_ms, origin_allowed
from .store import FirestoreRooms, StoreError
from .quota_guard import quota
from .publish_signal import wait_for_publish_or_frame
from .live_relay import MAX_FRAME, LiveError, live_enabled
from .defense_hints import decorated_view, receive_hint

logger = logging.getLogger(__name__)


def _store() -> FirestoreRooms:
    from firebase_admin import firestore, get_app

    return FirestoreRooms(firestore.client(app=get_app("portfolio-lab")))


def _verified_view(
    ticket: Ticket, verify: Callable[[str], tuple[str, bool]]
) -> tuple[FirestoreRooms, dict]:
    if not enabled() or not origin_allowed(ticket.origin):
        raise HTTPException(403, "Realtime unavailable")
    uid, owner = verify(ticket.authorization)
    if uid != ticket.uid:
        raise HTTPException(403, "Access denied")
    store = _store()
    with hub.commit_lock:
        view = store.view(ticket.room, uid, owner=owner)
        if view.get("my_seat") != ticket.seat:
            if view.get("my_seat") in (0, 1, 2):
                raise HubError("Seat changed; reconnect")
            raise HTTPException(403, "Seat denied")
        return store, view


def _connect(
    ticket: Ticket, verify: Callable[[str], tuple[str, bool]]
) -> tuple[FirestoreRooms, str]:
    # Keep the initial read and registration ordered with local commits.
    with hub.commit_lock:
        store, view = _verified_view(ticket, verify)
        connection = hub.connect(ticket, view, now_ms())
    return store, connection


def _revalidate(ticket: Ticket, connection: str, verify: Callable[[str], tuple[str, bool]]) -> None:
    if not enabled() or not origin_allowed(ticket.origin):
        raise HTTPException(403, "Realtime unavailable")
    uid, owner = verify(ticket.authorization)
    if uid != ticket.uid:
        raise HTTPException(403, "Access denied")
    with hub.commit_lock:
        cached = hub.snapshot(ticket, connection, now_ms())
        # Unchanged version reads only the room document, not all private state.
        # owner=False intentionally enforces actual membership even for Owner.
        view = _store().view(
            ticket.room, uid, owner=False, since_version=cached["version"] if cached else None
        )
        if view.get("unchanged"):
            return
        if view.get("my_seat") != ticket.seat:
            if view.get("my_seat") in (0, 1, 2):
                raise HubError("Seat changed; reconnect")
            raise HTTPException(403, "Seat denied")
        if owner:
            view["room_admin"] = True
        with hub.lock:
            if not hub.current(ticket, connection, now_ms()):
                raise HubError("Connection replaced")
            hub._accept_view(hub.rooms[ticket.room], ticket.uid, view)


def _sync(store: FirestoreRooms, ticket: Ticket) -> None:
    quota.require_available()
    at = now_ms()
    if not hub.due(ticket.room, at):
        return
    signature = tuple(s == "online" for s in hub.statuses(ticket.room, at))
    ok = False
    try:
        store.sync_realtime(ticket.room, ticket.uid)
        ok = True
    except Exception as exc:
        quota.record_failure(exc)
        raise
    finally:
        hub.synced(ticket.room, now_ms(), ok, signature)


def _live_room(ticket: Ticket, connection: str, at: int):
    # Caller holds the hub lock. The active lease is the authenticated identity;
    # never use a seat, connection, room or sender identifier from a media frame.
    if not live_enabled() or not hub.current(ticket, connection, at):
        raise LiveError("Media unavailable")
    room = hub.rooms[ticket.room]
    active = {
        seat: lease.connection
        for seat, lease in room.leases.items()
        if lease.connection is not None and lease.live(at)
    }
    room.live_media.prune(active, at)
    return room.live_media


def _media_receive(ticket: Ticket, connection: str, frame: dict, at: int) -> None:
    with hub.lock:
        relay = _live_room(ticket, connection, at)
        if hub.rooms[ticket.room].views.get(ticket.uid, {}).get("status") == "archived":
            raise LiveError("Media unavailable")
        relay.receive(ticket.seat, connection, frame, at)


def _media_delivery(ticket: Ticket, connection: str, at: int):
    with hub.lock:
        relay = _live_room(ticket, connection, at)
        return relay.snapshot(ticket.seat, connection), relay.drain(ticket.seat, connection)


def _media_prune(ticket: Ticket, at: int) -> None:
    with hub.lock:
        room = hub.rooms.get(ticket.room)
        if room:
            room.live_media.prune(
                {
                    seat: lease.connection
                    for seat, lease in room.leases.items()
                    if lease.connection is not None and lease.live(at)
                },
                at,
            )


async def _receive(socket: WebSocket) -> dict:
    message = await socket.receive_text()
    if len(message) > MAX_FRAME:
        raise HubError("Frame too large")
    try:
        value = json.loads(message)
    except (ValueError, TypeError) as exc:
        raise HubError("Invalid frame") from exc
    if not isinstance(value, dict):
        raise HubError("Invalid frame")
    if len(message) > 1024 and not (
        isinstance(value.get("type"), str) and value["type"].startswith("media_")
    ):
        raise HubError("Frame too large")
    return value


async def _send(socket: WebSocket, message: dict) -> None:
    # Latest-snapshot coalescing, no unbounded queue; slow peers reconnect.
    serialized = json.dumps(message, separators=(",", ":"), ensure_ascii=True)
    if len(serialized) > 96_000:
        raise HubError("Snapshot too large")
    await asyncio.wait_for(socket.send_text(serialized), timeout=3)


def make_realtime_router(verify: Callable[[str], tuple[str, bool]]) -> APIRouter:
    router = APIRouter(prefix="/preferans", tags=["Preferans realtime"])

    @router.websocket("/rooms/{room_id}/realtime")
    async def realtime(socket: WebSocket, room_id: str) -> None:
        origin = socket.headers.get("origin", "")
        if not enabled() or not origin_allowed(origin) or not hub.reserve_handshake():
            await socket.close(code=4403)
            return
        pending = True
        ticket: Ticket | None = None
        connection: str | None = None
        store: FirestoreRooms | None = None
        reader: asyncio.Task | None = None
        unsubscribe: Callable[[], None] | None = None
        close_code = 1000
        close_stage = "handshake"
        try:
            await socket.accept()
            auth = await asyncio.wait_for(_receive(socket), timeout=5)
            if (
                set(auth) != {"type", "ticket", "protocol"}
                or auth.get("type") != "authenticate"
                or auth.get("protocol") != PROTOCOL
                or not isinstance(auth.get("ticket"), str)
                or len(auth["ticket"]) > 128
            ):
                raise HubError("Invalid authentication")
            ticket = hub.redeem(auth["ticket"], room_id, origin, now_ms())
            quota.require_available()
            store, connection = await run_in_threadpool(_connect, ticket, verify)
            hub.release_handshake()
            pending = False
            await run_in_threadpool(_sync, store, ticket)
            last_version = -1
            last_hints = None
            last_hint_at = -1_000
            last_presence: list[str] | None = None
            last_ping = 0
            last_media = None
            last_media_error = None
            last_auth = now_ms()
            reader = asyncio.create_task(_receive(socket))
            wake = asyncio.Event()
            loop = asyncio.get_running_loop()
            unsubscribe = hub.publish_signal.subscribe(
                room_id, lambda: loop.call_soon_threadsafe(wake.set)
            )
            while True:
                close_stage = "lease"
                wake.clear()
                at = now_ms()
                if (
                    not enabled()
                    or not origin_allowed(origin)
                    or not hub.current(ticket, connection, at)
                ):
                    raise HubError("Connection expired")
                close_stage = "quota"
                quota.require_available()
                if at - last_auth >= AUTH_MS:
                    close_stage = "reauthorize"
                    await run_in_threadpool(_revalidate, ticket, connection, verify)
                    last_auth = now_ms()
                # Only transitions, timer deadlines and rare active timer checkpoints
                # cause a Firestore transaction. Never one transaction per WS ping.
                if hub.due(room_id, at, claim=False):
                    close_stage = "reconcile"
                    await run_in_threadpool(_sync, store, ticket)
                close_stage = "delivery"
                view = hub.snapshot(ticket, connection, now_ms())
                presence = hub.statuses(room_id, now_ms())
                if view:
                    with hub.lock:
                        view = decorated_view(hub.rooms[room_id], view)
                hints = view.get("defense_hints") if view else None
                if view and (view["version"] > last_version or hints != last_hints):
                    await _send(
                        socket,
                        {
                            "type": "snapshot",
                            "protocol": PROTOCOL,
                            "view": view,
                            "live_media": live_enabled(),
                            "presence": presence,
                            "server_now_ms": now_ms(),
                        },
                    )
                    last_version = view["version"]
                    last_hints = hints
                    last_presence = presence
                    with hub.lock:
                        hub.metrics["snapshots_sent"] += 1
                elif presence != last_presence:
                    await _send(
                        socket,
                        {
                            "type": "presence",
                            "protocol": PROTOCOL,
                            "presence": presence,
                            "server_now_ms": now_ms(),
                        },
                    )
                    last_presence = presence
                if live_enabled():
                    roster, messages = _media_delivery(ticket, connection, now_ms())
                    if roster != last_media:
                        last_media = roster
                        if roster is not None:
                            await _send(
                                socket,
                                {
                                    "type": "media_state",
                                    "protocol": PROTOCOL,
                                    "participants": roster,
                                    "server_now_ms": now_ms(),
                                },
                            )
                    for message in messages:
                        await _send(
                            socket, {**message, "protocol": PROTOCOL, "server_now_ms": now_ms()}
                        )
                close_stage = "receive"
                if await wait_for_publish_or_frame(reader, wake):
                    frame = reader.result()
                    at = now_ms()
                    if isinstance(frame.get("type"), str) and frame["type"].startswith("media_"):
                        try:
                            _media_receive(ticket, connection, frame, at)
                        except LiveError:
                            # A bad or stale media command cannot close the game socket.
                            # Coalesce errors under a flood; do not echo the payload.
                            if last_media_error is None or at - last_media_error >= 5_000:
                                last_media_error = at
                                await _send(
                                    socket,
                                    {
                                        "type": "media_error",
                                        "protocol": PROTOCOL,
                                        "server_now_ms": at,
                                    },
                                )
                        reader = asyncio.create_task(_receive(socket))
                        continue
                    if frame.get("type") == "defense_hint":
                        # Invalid/late presentation cues never close a healthy game socket.
                        if at - last_hint_at >= 125:
                            last_hint_at = at
                            with hub.lock:
                                if hub.current(ticket, connection, at):
                                    receive_hint(hub.rooms[room_id], ticket.uid, frame)
                            hub.publish_signal.notify(room_id)
                        reader = asyncio.create_task(_receive(socket))
                        continue
                    if frame != {"type": "ping", "protocol": PROTOCOL} or (
                        last_ping and at - last_ping < 2_000
                    ):
                        raise HubError("Invalid heartbeat")
                    hub.heartbeat(ticket, connection, at)
                    last_ping = at
                    await _send(socket, {"type": "pong", "protocol": PROTOCOL, "server_now_ms": at})
                    reader = asyncio.create_task(_receive(socket))
        except WebSocketDisconnect as exc:
            logger.info("preferans.realtime.peer_closed code=%s", exc.code)
        except HTTPException as exc:
            quota.record_failure(exc)
            close_code = (
                4401 if exc.status_code == 401 else 4403 if exc.status_code in (403, 404) else 1011
            )
        except StoreError as exc:
            quota.record_failure(exc)
            close_code = 4403 if exc.code in (403, 404) else 1011
        except (HubError, asyncio.TimeoutError, RuntimeError, ValueError) as exc:
            close_code = 1011 if quota.record_failure(exc) else 4408
        except Exception as exc:
            quota.record_failure(exc)
            # Never log credential, frame contents, room state or provider traceback.
            logger.warning("preferans.realtime.failed")
            close_code = 1011
        finally:
            if close_code != 1000:
                # Fixed category and code only: never log tickets, cards, UIDs or raw exceptions.
                logger.warning(
                    "preferans.realtime.closed code=%s stage=%s", close_code, close_stage
                )
            if unsubscribe is not None:
                unsubscribe()
            if pending:
                hub.release_handshake()
            if reader:
                reader.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await reader
            if ticket and connection:
                hub.disconnect(ticket, connection, now_ms())
                _media_prune(ticket, now_ms())
                if store:
                    with contextlib.suppress(Exception):
                        await run_in_threadpool(_sync, store, ticket)
            with contextlib.suppress(Exception):
                await socket.close(code=close_code)

    return router
