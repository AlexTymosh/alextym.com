"""Ephemeral seat-scoped signalling. Called under the existing hub lock.

No SDK, persistent state, credentials or media bytes. Connection identifiers
come from the authenticated room hub, never from a client frame.
"""

from __future__ import annotations

import json
import os
import secrets
from collections import deque
from dataclasses import dataclass, field

MAX_FRAME = 16_384
MAX_QUEUE = 64
SIGNAL_TTL_MS = 15_000
WINDOW_MS = 10_000
MAX_WINDOW = 100


def live_enabled() -> bool:
    return (
        os.getenv("PREFERANS_MEDIA_ENABLED") == "true"
        and os.getenv("PREFERANS_LIVE_MEDIA_WS_ENABLED") == "true"
    )


class LiveError(ValueError):
    """Safe, fixed error; no SDP/ICE details in exception messages."""


@dataclass
class Participant:
    connection: str
    session: str = field(default_factory=lambda: secrets.token_hex(16))
    audio: bool = False
    video: bool = False
    messages: deque = field(default_factory=deque)


def signal_data(kind: object, value: object) -> dict:
    if not isinstance(value, dict):
        raise LiveError("Invalid signal")
    if kind in ("offer", "answer"):
        if (
            set(value) != {"type", "sdp"}
            or value["type"] != kind
            or not isinstance(value["sdp"], str)
            or not 0 < len(value["sdp"]) <= 12_000
        ):
            raise LiveError("Invalid SDP")
    elif kind == "ice":
        if not set(value) <= {"candidate", "sdpMid", "sdpMLineIndex", "usernameFragment"}:
            raise LiveError("Invalid ICE")
        candidate = value.get("candidate")
        if not isinstance(candidate, str) or not 0 < len(candidate) <= 2048:
            raise LiveError("Invalid ICE")
        for key in ("sdpMid", "usernameFragment"):
            if value.get(key) is not None and (
                not isinstance(value[key], str) or len(value[key]) > 256
            ):
                raise LiveError("Invalid ICE")
        index = value.get("sdpMLineIndex")
        if index is not None and (type(index) is not int or not 0 <= index <= 16):
            raise LiveError("Invalid ICE")
    else:
        raise LiveError("Invalid signal kind")
    if len(json.dumps(value, ensure_ascii=True, separators=(",", ":"))) > MAX_FRAME - 1024:
        raise LiveError("Signal too large")
    return value.copy()


class LiveRelay:
    def __init__(self) -> None:
        self.members: dict[int, Participant] = {}
        self.rates: dict[str, tuple[int, int]] = {}
        self.dropped = 0

    def prune(self, active: dict[int, str], at: int) -> None:
        for seat, participant in list(self.members.items()):
            if active.get(seat) != participant.connection:
                del self.members[seat]
        for connection in list(self.rates):
            if connection not in active.values():
                del self.rates[connection]
        for participant in self.members.values():
            if not participant.messages:
                continue
            participant.messages = deque(
                (expiry, frame)
                for expiry, frame in participant.messages
                if expiry > at
                and frame["from"] in self.members
                and self.members[frame["from"]].session == frame["from_session"]
            )

    def snapshot(self, seat: int, connection: str) -> list[dict | None] | None:
        member = self.members.get(seat)
        if not member or member.connection != connection:
            return None
        return [
            {"session": p.session, "audio": p.audio, "video": p.video} if p else None
            for p in (self.members.get(i) for i in range(3))
        ]

    def receive(self, seat: int, connection: str, frame: dict, at: int) -> None:
        # Leaving must remain available even after exceeding a rate limit.
        if frame == {"type": "media_leave", "protocol": 1} and type(frame.get("protocol")) is int:
            member = self.members.get(seat)
            if member and member.connection == connection:
                del self.members[seat]
            return
        start, count = self.rates.get(connection, (at, 0))
        if at - start >= WINDOW_MS:
            start, count = at, 0
        if count >= MAX_WINDOW:
            raise LiveError("Media rate limit")
        self.rates[connection] = (start, count + 1)
        kind = frame.get("type")
        base = {"type", "protocol"}
        if type(frame.get("protocol")) is not int or frame["protocol"] != 1:
            raise LiveError("Invalid media protocol")
        if kind == "media_join" and set(frame) == base:
            # Each explicit join begins a fresh generation, including recovery
            # after an unacknowledged leave. No credentials in the public roster.
            self.members[seat] = Participant(connection)
            return
        member = self.members.get(seat)
        if not member or member.connection != connection:
            raise LiveError("Join media first")
        if kind == "media_presence" and set(frame) == base | {"audio", "video"}:
            if type(frame["audio"]) is not bool or type(frame["video"]) is not bool:
                raise LiveError("Invalid media presence")
            member.audio, member.video = frame["audio"], frame["video"]
            return
        if kind != "media_signal" or set(frame) != base | {"to", "to_session", "kind", "data"}:
            raise LiveError("Invalid media command")
        to = frame["to"]
        if type(to) is not int or to not in range(3) or to == seat:
            raise LiveError("Invalid media recipient")
        data = signal_data(frame["kind"], frame["data"])
        target = self.members.get(to)
        # Negotiation may race with a disconnect. Drop stale messages, not the game socket.
        if target is None or target.session != frame["to_session"]:
            self.dropped += 1
            return
        if len(target.messages) >= MAX_QUEUE:
            self.dropped += 1
            raise LiveError("Media queue full")
        target.messages.append(
            (
                at + SIGNAL_TTL_MS,
                {
                    "type": "media_signal",
                    "from": seat,
                    "from_session": member.session,
                    "to_session": target.session,
                    "kind": frame["kind"],
                    "data": data,
                },
            )
        )

    def drain(self, seat: int, connection: str) -> list[dict]:
        member = self.members.get(seat)
        if not member or member.connection != connection:
            return []
        # Limit a single socket tick to eight signalling messages.
        return [member.messages.popleft()[1] for _ in range(min(8, len(member.messages)))]
