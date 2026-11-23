"""Bounded, server-only P2P signalling and unanimous recording consent.

No media bytes are accepted or stored. Firestore contains short-lived, recipient-
scoped SDP/ICE control messages only. Every operation verifies a seated player.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from preferans.online.store import StoreError, _fingerprint, _get, _key, _room_id

SIGNAL_LIFETIME_MS = 90_000
PRESENCE_LIFETIME_MS = 45_000
MAX_SIGNALS = 64
MAX_PAYLOAD = 6_000


def _empty() -> dict:
    return {
        "version": 0,
        "participants": [{"audio": False, "video": False, "at_ms": 0} for _ in range(3)],
        "signals": [],
        "presence_tokens": [None, None, None],
        "recording": None,
    }


def _seat(room: dict | None, uid: str) -> int:
    if not isinstance(room, dict) or not isinstance(room.get("seats"), list):
        raise StoreError(404, "Not found")
    seats = room["seats"]
    if len(seats) != 3 or None in seats or uid not in seats:
        raise StoreError(404, "Not found")
    return seats.index(uid)


def _presence(state: dict, now: int) -> list[dict]:
    return [
        {
            "audio": bool(p["audio"]) if now - p["at_ms"] < PRESENCE_LIFETIME_MS else False,
            "video": bool(p["video"]) if now - p["at_ms"] < PRESENCE_LIFETIME_MS else False,
        }
        for p in state["participants"]
    ]


def _recording_for_client(record: dict | None) -> dict | None:
    if record is None:
        return None
    return {
        "id": record["id"],
        "initiator": record["initiator"],
        "status": record["status"],
        "votes": list(record["votes"]),
    }


def _signal_data(kind: str, payload: object) -> dict:
    if kind not in {"offer", "answer", "ice", "restart"}:
        raise StoreError(422, "Invalid signal type")
    if not isinstance(payload, dict):
        raise StoreError(422, "Invalid signal data")
    if len(json.dumps(payload, separators=(",", ":"))) > MAX_PAYLOAD:
        raise StoreError(413, "Signal too large")
    if kind in {"offer", "answer"}:
        if set(payload) != {"type", "sdp"}:
            raise StoreError(422, "Invalid SDP schema")
        if payload["type"] != kind or not isinstance(payload["sdp"], str):
            raise StoreError(422, "Invalid SDP")
        if not 1 <= len(payload["sdp"]) <= 5_800:
            raise StoreError(422, "Invalid SDP length")
    elif kind == "ice":
        if not set(payload) <= {"candidate", "sdpMid", "sdpMLineIndex", "usernameFragment"}:
            raise StoreError(422, "Invalid ICE schema")
        if not isinstance(payload.get("candidate"), str):
            raise StoreError(422, "Invalid ICE candidate")
        if len(payload["candidate"]) > 2_048:
            raise StoreError(413, "ICE too large")
    elif payload:
        raise StoreError(422, "Restart has no payload")
    return payload


class MediaRooms:
    """Independent Firestore document so media polling never touches card state."""

    def __init__(self, db: Any, *, firestore_module: Any = None, now_ms=None):
        self.db = db
        self.now_ms = now_ms or (lambda: int(time.time() * 1_000))
        if firestore_module is None:
            from firebase_admin import firestore

            firestore_module = firestore
        self.fs = firestore_module

    def _refs(self, room_id: str):
        _room_id(room_id)
        room = self.db.collection("preferans_rooms").document(room_id)
        media = room.collection("media").document("current")
        return room, media

    def view(self, room_id: str, uid: str, *, cursor: int = 0) -> dict:
        if type(cursor) is not int or not 0 <= cursor <= 2_147_483_647:
            raise StoreError(422, "Invalid cursor")
        room_ref, media_ref = self._refs(room_id)
        room_snap = room_ref.get(timeout=5.0)
        room = room_snap.to_dict() if room_snap.exists else None
        seat = _seat(room, uid)
        media_snap = media_ref.get(timeout=5.0)
        state = media_snap.to_dict() if media_snap.exists else _empty()
        now = self.now_ms()
        messages = [
            {"sequence": s["sequence"], "from": s["from"], "kind": s["kind"], "data": s["data"]}
            for s in state["signals"]
            if s["to"] == seat and s["sequence"] > cursor and s["at_ms"] + SIGNAL_LIFETIME_MS > now
        ]
        return {
            "room_id": room_id,
            "seat": seat,
            "version": state["version"],
            "participants": _presence(state, now),
            "recording": _recording_for_client(state["recording"]),
            "signals": messages,
        }

    def command(self, room_id: str, uid: str, token: str, action: str, args: dict) -> dict:
        if (
            action
            not in {
                "presence",
                "signal",
                "record_request",
                "record_vote",
                "record_start",
                "record_stop",
            }
            or not isinstance(args, dict)
            or len(args) > 5
        ):
            raise StoreError(422, "Invalid media command")
        op_id = _key(uid, token)
        signature = _fingerprint({"room": room_id, "action": action, "args": args})
        room_ref, media_ref = self._refs(room_id)
        operation_ref = room_ref.collection("media_operations").document(op_id)
        tx = self.db.transaction()

        @self.fs.transactional
        def commit(transaction):
            previous = _get(transaction, operation_ref) if action != "presence" else None
            room = _get(transaction, room_ref)
            seat = _seat(room, uid)
            if previous:
                if previous["fingerprint"] != signature:
                    raise StoreError(409, "Conflicting idempotency key")
                return previous["response"]
            state = _get(transaction, media_ref) or _empty()
            state = dict(state)
            now = self.now_ms()
            state["signals"] = [
                s for s in state["signals"] if s["at_ms"] + SIGNAL_LIFETIME_MS > now
            ][-MAX_SIGNALS:]
            state["participants"] = [dict(p) for p in state["participants"]]
            record = dict(state["recording"]) if state["recording"] else None
            if action == "presence":
                if state.get("presence_tokens", [None] * 3)[seat] == op_id:
                    return {"room_id": room_id, "version": state["version"], "ok": True}
                if set(args) != {"audio", "video"} or any(
                    type(args[x]) is not bool for x in ("audio", "video")
                ):
                    raise StoreError(422, "Invalid media presence")
                state["participants"][seat] = {
                    "audio": args["audio"],
                    "video": args["video"],
                    "at_ms": now,
                }
                state.setdefault("presence_tokens", [None] * 3)[seat] = op_id
                # Loss of a media source cannot silently continue application recording.
                if not (args["audio"] or args["video"]) and record and record["status"] == "active":
                    record["status"] = "stopped"
            elif action == "signal":
                if set(args) != {"to", "kind", "data"}:
                    raise StoreError(422, "Invalid signal fields")
                to = args["to"]
                if type(to) is not int or to not in range(3) or to == seat:
                    raise StoreError(422, "Invalid peer")
                if not any(_presence(state, now)[seat].values()):
                    raise StoreError(409, "Activate media before signalling")
                data = _signal_data(args["kind"], args["data"])
                state["signals"].append(
                    {
                        "sequence": state["version"] + 1,
                        "from": seat,
                        "to": to,
                        "kind": args["kind"],
                        "data": data,
                        "at_ms": now,
                    }
                )
                state["signals"] = state["signals"][-MAX_SIGNALS:]
            elif action == "record_request":
                if args or record and record["status"] in {"requested", "ready", "active"}:
                    raise StoreError(409, "Recording session already pending or active")
                if not all(any(p.values()) for p in _presence(state, now)):
                    raise StoreError(409, "All players must connect media first")
                record = {
                    "id": hashlib.sha256(f"{room_id}:{op_id}".encode()).hexdigest()[:24],
                    "initiator": seat,
                    "status": "requested",
                    "votes": [None, None, None],
                }
                record["votes"][seat] = True
            elif action == "record_vote":
                if set(args) != {"approve"} or type(args["approve"]) is not bool:
                    raise StoreError(422, "Invalid recording vote")
                if not record or record["status"] not in {"requested", "ready", "active"}:
                    raise StoreError(409, "No pending recording session")
                if args["approve"] is False:
                    record["votes"][seat] = False
                    record["status"] = "stopped"
                elif record["status"] != "requested":
                    raise StoreError(409, "Cannot change consent after approval")
                else:
                    record["votes"][seat] = True
                    if all(v is True for v in record["votes"]):
                        record["status"] = "ready"
            elif action == "record_start":
                if args or not record or record["status"] != "ready" or record["initiator"] != seat:
                    raise StoreError(409, "Not authorized to start recording")
                if not all(v is True for v in record["votes"]):
                    raise StoreError(409, "Unanimous consent required")
                if not all(any(p.values()) for p in _presence(state, now)):
                    raise StoreError(409, "Media participant disconnected")
                record["status"] = "active"
            else:
                if args or not record or record["status"] not in {"requested", "ready", "active"}:
                    raise StoreError(409, "No recording to stop")
                record["status"] = "stopped"
                record["votes"][seat] = False
            state["recording"] = record
            state["version"] += 1
            response = {"room_id": room_id, "version": state["version"], "ok": True}
            transaction.set(media_ref, state)
            if action != "presence":
                transaction.create(operation_ref, {"fingerprint": signature, "response": response})
            return response

        return commit(tx)
