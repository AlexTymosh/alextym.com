"""Bounded lobby directory and room-member-only profile projection.

No private game document is read. Account email is an optional room-member-only fallback; the directory never reads it.
"""

from __future__ import annotations

import re
import time
from typing import Any

from .realtime import enabled as realtime_enabled, hub

from google.cloud.firestore_v1.base_query import FieldFilter

from .store import ROOM_ID, StoreError
from .quota_guard import is_quota_error

LIMIT = 100
STATUSES = {"lobby", "playing", "awaiting_settlement", "between", "closed", "archived"}
AVATAR = re.compile(r"data:image/webp;base64,[A-Za-z0-9+/=]+\Z")


def can_create_room(role: object, owner: bool) -> bool:
    return owner is True or role == "Admin"


def _valid_room(room: object) -> bool:
    return (
        isinstance(room, dict)
        and isinstance(room.get("id"), str)
        and ROOM_ID.fullmatch(room["id"]) is not None
        and room.get("status") in STATUSES
        and isinstance(room.get("seats"), list)
        and len(room["seats"]) == 3
        and all(s is None or isinstance(s, str) and s and "/" not in s for s in room["seats"])
    )


def directory(db: Any, uid: str, *, admin: bool) -> dict:
    if not uid or "/" in uid:
        raise StoreError(403, "Access denied")
    collection = db.collection("preferans_rooms")
    # Two single-field indexed queries. Never scan all private/finished rooms.
    mine = list(
        collection.where(filter=FieldFilter("seats", "array_contains", uid))
        .limit(LIMIT + 1)
        .stream(timeout=5.0)
    )
    waiting = list(
        collection.where(filter=FieldFilter("status", "==", "lobby"))
        .limit(LIMIT + 1)
        .stream(timeout=5.0)
    )
    result: dict[str, tuple[int, dict]] = {}
    cached_names: dict[str, str | None] = {}
    at = int(time.time() * 1000)
    for row in [*mine[:LIMIT], *waiting[:LIMIT]]:
        room = row.to_dict()
        if not _valid_room(room) or room["status"] in {"closed", "archived"}:
            continue
        own = uid in room["seats"]
        if not own and not (room["status"] == "lobby" and None in room["seats"]):
            continue
        created = room.get("created_at_ms")
        waiting_names = []
        player_names = []
        # Only accessible rooms. Reuse the existing per-request read budget.
        # A seated player is not necessarily connected; live presence remains separate.
        presence = (
            hub.presence(room["id"], room["seats"], at)
            if room["status"] == "lobby" and realtime_enabled()
            else [None, None, None]
        )
        for seat, seen in zip(room["seats"], presence):
            if seat is None:
                player_names.append(None)
                continue
            if seat not in cached_names and len(cached_names) < 30:
                try:
                    snap = db.collection("portfolio_lab_profiles").document(seat).get(timeout=5.0)
                    cached_names[seat] = profile_projection(
                        snap.to_dict() if snap.exists else None
                    )["name"]
                except Exception as exc:
                    if is_quota_error(exc):
                        raise
                    cached_names[seat] = None
            name = cached_names.get(seat)
            player_names.append(name)
            if name and seen is not None:
                waiting_names.append(name)
        result[room["id"]] = (
            created if type(created) is int else 0,
            {
                "room_id": room["id"],
                "status": room["status"],
                "occupied": [s is not None for s in room["seats"]],
                "mine": own,
                "created_at_ms": created if type(created) is int and created > 0 else None,
                "daily_number": room.get("daily_number"),
                "waiting_names": waiting_names,
                "player_names": player_names,
            },
        )
    rooms = [
        value
        for _, value in sorted(
            result.values(), key=lambda pair: (not pair[1]["mine"], -pair[0], pair[1]["room_id"])
        )
    ]
    return {
        "rooms": rooms,
        "can_create": admin,
        "truncated": len(mine) > LIMIT or len(waiting) > LIMIT,
    }


def profile_projection(record: object) -> dict:
    if not isinstance(record, dict):
        return {"name": None, "avatar": None}
    parts = []
    for key in ("first_name", "last_name"):
        value = record.get(key)
        if (
            isinstance(value, str)
            and len(value) <= 80
            and not re.search(r"[@\x00-\x1f\x7f-\x9f]", value)
        ):
            parts.append(value.strip())
    avatar = record.get("avatar_data_url") if record.get("avatar_source") == "upload" else None
    if not isinstance(avatar, str) or len(avatar) > 133_400 or not AVATAR.fullmatch(avatar):
        avatar = None
    # Do not return provider URLs, email fallbacks, linked providers or UID.
    return {"name": " ".join(p for p in parts if p) or None, "avatar": avatar}


def room_profiles(db: Any, room_id: str, uid: str, *, email_lookup=None) -> dict:
    if not ROOM_ID.fullmatch(room_id) or not uid or "/" in uid:
        raise StoreError(404, "Not found")
    snapshot = db.collection("preferans_rooms").document(room_id).get(timeout=5.0)
    room = snapshot.to_dict() if snapshot.exists else None
    if not _valid_room(room) or uid not in room["seats"]:
        raise StoreError(404, "Not found")
    profiles = []
    for seat in room["seats"]:
        record = None
        if seat is not None:
            snap = db.collection("portfolio_lab_profiles").document(seat).get(timeout=5.0)
            record = snap.to_dict() if snap.exists else None
        profile = profile_projection(record)
        if seat is not None and not profile["name"] and email_lookup is not None:
            email = email_lookup(seat)
            if (
                isinstance(email, str)
                and len(email) <= 254
                and re.fullmatch(r"[^@\s\x00-\x1f]+@[^@\s\x00-\x1f]+", email)
            ):
                profile["email"] = email
        profiles.append(profile)
    return {"profiles": profiles}
