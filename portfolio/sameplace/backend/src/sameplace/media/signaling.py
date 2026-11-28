"""Bounded ephemeral WebRTC signaling, colocated with the single-worker meeting hub."""

import json
import os
import re
from dataclasses import dataclass, field
from secrets import token_hex
from itertools import combinations
from typing import Any

MAX_MEDIA_FRAME = 32768
MAX_SDP = 24000
MAX_PENDING = 96
MAX_QUEUE_BYTES = 128 * 1024
MAX_SIGNALS = 240
ID = re.compile(r"[a-f0-9]{32}\Z")
STUN = re.compile(r"stuns?:[a-zA-Z0-9.-]+(?::[0-9]{1,5})?\Z")


def configured_media():
    return os.getenv("SAMEPLACE_MEDIA_ENABLED") == "true"


def configured_media_capacity():
    # A two-person trial ceiling is a safe initial configuration, not verified capacity.
    try:
        value = int(os.getenv("SAMEPLACE_MEDIA_CAPACITY", "2"))
    except ValueError:
        return 2
    return value if 2 <= value <= 10 else 2


def configured_stun():
    # No implicit third-party network traffic and no TURN credentials.
    value = os.getenv("SAMEPLACE_STUN_URL", "").strip()
    if value and STUN.fullmatch(value):
        return [{"urls": value}]
    return []


@dataclass
class Endpoint:
    connection: str
    public_id: str
    inbox: list[dict] = field(default_factory=list)
    window_start: float = 0
    count: int = 0
    microphone: bool = False
    camera: bool = False


@dataclass
class Session:
    mode: str = "room"
    endpoints: dict[str, Endpoint] = field(default_factory=dict)
    muted: set[str] = field(default_factory=set)
    pairs: dict[tuple[str, str], str] = field(default_factory=dict)


class MediaState:
    """All operations share the meeting lock. No authorization cache or durable writes.

    Public peer IDs identify already admitted people. Pair IDs are rotated on
    membership/channel changes, never used as credentials. Queues are bounded.
    """

    def __init__(
        self,
        hub,
        enabled=configured_media,
        ice_servers=configured_stun,
        capacity=configured_media_capacity,
    ):
        self.hub = hub
        self.enabled = enabled
        self.ice_servers = ice_servers
        self.capacity = capacity
        self.sessions: dict[str, Session] = {}
        self.hub.media_observer = self.observe

    def observe(self, meeting):
        # Called under Hub.lock on location / membership changes. No callbacks
        # into cleanup; keep channel changes atomic with the authoritative roster.
        if meeting.id in self.sessions:
            self._reconcile(meeting, self.sessions[meeting.id])

    def _reconcile(self, meeting, session):
        for uid, endpoint in list(session.endpoints.items()):
            person = meeting.people.get(uid)
            if not person or endpoint.connection not in person.connections:
                del session.endpoints[uid]
        # Keep moderation for the duration of this meeting (including reconnects),
        # but never allow unbounded accumulation of historical UIDs.
        allowed = set()
        for left, right in combinations(sorted(session.endpoints), 2):
            if (
                session.mode == "room"
                or meeting.people[left].location == meeting.people[right].location
            ):
                allowed.add((left, right))
        session.pairs = {
            key: session.pairs[key] if key in session.pairs else token_hex(16)
            for key in sorted(allowed)
        }
        valid = set(session.pairs.values())
        for endpoint in session.endpoints.values():
            endpoint.inbox = [frame for frame in endpoint.inbox if frame["pair"] in valid]

    def _meeting(self, slug, uid, connection):
        if not self.hub.alive(slug, uid, connection):
            return None
        return self.hub.meetings[slug]

    def _session(self, meeting):
        alive = {m.id for m in self.hub.meetings.values()}
        for key in list(self.sessions):
            if key not in alive:
                del self.sessions[key]
        return self.sessions.setdefault(meeting.id, Session())

    def state(self, slug, uid, connection):
        with self.hub.lock:
            meeting = self._meeting(slug, uid, connection)
            if not meeting or not self.enabled():
                if not self.enabled():
                    self.sessions.clear()
                return None, []
            session = self._session(meeting)
            self._reconcile(meeting, session)
            own = session.endpoints.get(uid)
            joined = own is not None and own.connection == connection
            peers = []
            if joined:
                for key, pair in session.pairs.items():
                    if uid not in key:
                        continue
                    other = key[1] if key[0] == uid else key[0]
                    peers.append(
                        {
                            "id": session.endpoints[other].public_id,
                            "pair": pair,
                            "offerer": uid == key[0],
                            "muted": other in session.muted,
                            "microphone": session.endpoints[other].microphone
                            and other not in session.muted,
                            "camera": session.endpoints[other].camera,
                        }
                    )
            result = {
                "type": "media.state",
                "meeting_id": meeting.id,
                "mode": session.mode,
                "joined": joined,
                "occupied": own is not None and not joined,
                "muted": uid in session.muted,
                "peers": peers,
                "ice_servers": self.ice_servers(),
            }
            messages = own.inbox[:] if joined else []
            if joined:
                own.inbox.clear()
            return result, messages

    def disconnect(self, slug, uid, connection):
        with self.hub.lock:
            meeting = self.hub.meetings.get(slug)
            if not meeting:
                return
            session = self.sessions.get(meeting.id)
            if (
                session
                and uid in session.endpoints
                and session.endpoints[uid].connection == connection
            ):
                del session.endpoints[uid]
                self._reconcile(meeting, session)

    def command(self, slug, uid, connection, frame, permission=None):
        """Return a stable error code (never echo SDP, ICE or credentials)."""
        with self.hub.lock:
            meeting = self._meeting(slug, uid, connection)
            if not meeting or not self.enabled():
                return "MEDIA_DISABLED"
            session = self._session(meeting)
            self._reconcile(meeting, session)
            kind = frame.get("type")
            own = session.endpoints.get(uid)
            if kind == "media.join" and set(frame) == {"type"}:
                if own and own.connection != connection:
                    return "MEDIA_TAB_LIMIT"
                if not own:
                    if len(meeting.people) > self.capacity():
                        return "MEDIA_CAPACITY"
                    session.endpoints[uid] = Endpoint(
                        connection, meeting.people[uid].public_id, window_start=self.hub.clock()
                    )
                    self._reconcile(meeting, session)
                return None
            if kind == "media.leave" and set(frame) == {"type"}:
                self.disconnect(slug, uid, connection)
                return None
            if kind == "media.mode" and set(frame) == {"type", "mode"}:
                if not permission or not permission.get("channel"):
                    return "MEDIA_DENIED"
                mode = frame["mode"]
                if mode not in ("room", "location"):
                    return "MEDIA_INVALID"
                if mode != session.mode:
                    session.mode = mode
                    self._reconcile(meeting, session)
                return None
            if kind == "media.mute" and set(frame) == {"type", "target", "muted"}:
                target = frame["target"]
                if (
                    not isinstance(target, str)
                    or not ID.fullmatch(target)
                    or type(frame["muted"]) is not bool
                ):
                    return "MEDIA_INVALID"
                other = next(
                    (key for key, p in meeting.people.items() if p.public_id == target), None
                )
                if (
                    not permission
                    or not permission.get("moderate")
                    or other is None
                    or other == uid
                    or (other == permission.get("owner_uid") and not permission.get("owner"))
                ):
                    return "MEDIA_DENIED"
                if frame["muted"]:
                    if len(session.muted) >= 100 and other not in session.muted:
                        return "MEDIA_BUSY"
                    session.muted.add(other)
                    if other in session.endpoints:
                        session.endpoints[other].microphone = False
                else:
                    session.muted.discard(other)
                return None
            if kind == "media.tracks" and set(frame) == {"type", "microphone", "camera"}:
                if not own or own.connection != connection:
                    return "MEDIA_JOIN_REQUIRED"
                if type(frame["microphone"]) is not bool or type(frame["camera"]) is not bool:
                    return "MEDIA_INVALID"
                own.microphone = frame["microphone"] and uid not in session.muted
                own.camera = frame["camera"]
                return None
            if kind != "media.signal" or set(frame) != {"type", "target", "pair", "signal"}:
                return "MEDIA_INVALID"
            if not own or own.connection != connection:
                return "MEDIA_JOIN_REQUIRED"
            target, pair, signal = frame["target"], frame["pair"], frame["signal"]
            if (
                not isinstance(target, str)
                or not ID.fullmatch(target)
                or not isinstance(pair, str)
                or not ID.fullmatch(pair)
                or not valid_signal(signal)
            ):
                return "MEDIA_INVALID"
            other = next(
                (key for key, ep in session.endpoints.items() if ep.public_id == target), None
            )
            if (
                other is None
                or other == uid
                or session.pairs.get(tuple(sorted((uid, other)))) != pair
            ):
                return "MEDIA_STALE_PEER"
            now = self.hub.clock()
            if now - own.window_start >= 60:
                own.window_start, own.count = now, 0
            pending = session.endpoints[other].inbox
            message = {
                "type": "media.signal",
                "from": own.public_id,
                "pair": pair,
                "signal": signal,
            }
            if (
                own.count >= MAX_SIGNALS
                or len(pending) >= MAX_PENDING
                or sum(len(json.dumps(item, ensure_ascii=True)) for item in pending)
                + len(json.dumps(message, ensure_ascii=True))
                > MAX_QUEUE_BYTES
            ):
                return "MEDIA_BUSY"
            own.count += 1
            pending.append(message)
            return None


def valid_signal(signal: Any) -> bool:
    if not isinstance(signal, dict):
        return False
    kind = signal.get("kind")
    if kind in ("offer", "answer"):
        return (
            set(signal) == {"kind", "sdp"}
            and isinstance(signal["sdp"], str)
            and 1 <= len(signal["sdp"].encode("utf-8")) <= MAX_SDP
        )
    if kind != "ice" or set(signal) != {"kind", "candidate", "sdpMid", "sdpMLineIndex"}:
        return False
    candidate, mid, index = signal["candidate"], signal["sdpMid"], signal["sdpMLineIndex"]
    return (
        isinstance(candidate, str)
        and 0 < len(candidate) <= 2048
        and (mid is None or isinstance(mid, str) and len(mid) <= 64)
        and (index is None or type(index) is int and 0 <= index <= 16)
        and (mid is not None or index is not None)
    )
