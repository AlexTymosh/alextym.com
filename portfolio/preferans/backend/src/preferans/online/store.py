"""Firestore transactions for an authoritative, server-only three-seat room.

Firestore client access must be performed by an authenticated server. Every
mutation reads state under a transaction and compares a monotonic version.
The collection tree is entirely denied to browser Firestore SDK clients.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

from preferans.domain.auction import RuleViolation
from preferans.domain.cards import deal, shuffled_deck
from preferans.domain.game import GameState, Phase, start_game
from preferans.domain.history import final_result, update_ranking
from preferans.domain.ledger import ScoreState
from preferans.domain.scoring import RewardRoute, settle_game
from preferans.online.codec import decode, encode
from preferans.online.commands import apply_command, redacted_action
from preferans.online.controls import (
    ControlError,
    adjust_score,
    can_start_counter,
    configure_policy,
    fresh,
    pulse,
    reconcile,
    record_candidate,
    request_undo,
    start_counter,
    stop_counter,
    vote_undo,
)
from preferans.online.views import seat_view

ROOM_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass
class StoreError(Exception):
    code: int
    detail: str

    def __str__(self) -> str:
        return self.detail


def _key(uid: str, token: str) -> str:
    if not uid or "/" in uid or not isinstance(token, str) or not 8 <= len(token) <= 128:
        raise StoreError(422, "Invalid idempotency key")
    return hashlib.sha256(f"{uid}\x00{token}".encode()).hexdigest()


def _fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _room_id(room_id: str) -> None:
    if not isinstance(room_id, str) or not ROOM_ID.fullmatch(room_id):
        raise StoreError(404, "Not found")


def _member(room: dict, uid: str, *, admin: bool = False, owner: bool = False) -> int | None:
    if owner and admin:
        return None
    if admin and room["admin_uid"] == uid:
        return room["seats"].index(uid) if uid in room["seats"] else None
    if uid not in room["seats"]:
        raise StoreError(404, "Not found")
    return room["seats"].index(uid)


def _get(tx: Any, ref: Any) -> dict | None:
    snap = tx.get(ref)
    return snap.to_dict() if snap.exists else None


class FirestoreRooms:
    def __init__(self, db: Any, *, firestore_module: Any = None, now_ms=None):
        self.db = db
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))
        if firestore_module is None:
            from firebase_admin import firestore

            firestore_module = firestore
        self.fs = firestore_module

    def _room(self, room_id: str) -> Any:
        _room_id(room_id)
        return self.db.collection("preferans_rooms").document(room_id)

    def create(self, uid: str, token: str) -> dict:
        op_id = _key(uid, token)
        identity = _fingerprint({"kind": "create", "uid": uid})
        operation = self.db.collection("preferans_create_ops").document(op_id)
        room_id = uuid.uuid4().hex
        doc = self._room(room_id)
        private = doc.collection("private").document("current")
        tx = self.db.transaction()

        @self.fs.transactional
        def commit(transaction):
            previous = _get(transaction, operation)
            if previous:
                if previous.get("fingerprint") != identity:
                    raise StoreError(409, "Conflicting idempotency key")
                return previous["response"]
            room = {
                "id": room_id,
                "admin_uid": uid,
                "seats": [uid, None, None],
                "status": "lobby",
                "version": 0,
                "game_id": None,
                "dealer": None,
                "created_at_ms": self.now_ms(),
            }
            result = {"room_id": room_id, "version": 0, "my_seat": 0, "status": "lobby"}
            transaction.create(doc, room)
            transaction.create(
                private,
                {
                    "game": None,
                    "score": encode(ScoreState.new()),
                    "controls": fresh(),
                    "version": 0,
                },
            )
            transaction.create(operation, {"fingerprint": identity, "response": result})
            return result

        return commit(tx)

    def join(self, room_id: str, uid: str, token: str, expected_version: int) -> dict:
        return self._mutate(room_id, uid, token, expected_version, "join", {}, False)

    def start(self, room_id: str, uid: str, token: str, expected_version: int, owner: bool) -> dict:
        return self._mutate(room_id, uid, token, expected_version, "start", {}, owner)

    def command(
        self, room_id: str, uid: str, token: str, expected_version: int, action: str, args: dict
    ) -> dict:
        return self._mutate(room_id, uid, token, expected_version, action, args, False)

    def settle(
        self, room_id: str, uid: str, token: str, expected_version: int, args: dict, owner: bool
    ) -> dict:
        return self._mutate(room_id, uid, token, expected_version, "settle", args, owner)

    def admin_adjust(
        self, room_id: str, uid: str, token: str, expected_version: int, args: dict, owner: bool
    ) -> dict:
        return self._mutate(room_id, uid, token, expected_version, "score_adjust", args, owner)

    def _mutate(
        self,
        room_id: str,
        uid: str,
        token: str,
        expected_version: int,
        action: str,
        args: dict,
        owner: bool,
    ) -> dict:
        if type(expected_version) is not int or expected_version < 0:
            raise StoreError(422, "Invalid version")
        if not isinstance(args, dict):
            raise StoreError(422, "Invalid arguments")
        op_id = _key(uid, token)
        identity = _fingerprint(
            {"room": room_id, "action": action, "args": args, "expected_version": expected_version}
        )
        doc = self._room(room_id)
        private = doc.collection("private").document("current")
        operation = doc.collection("operations").document(op_id)
        tx = self.db.transaction()

        @self.fs.transactional
        def commit(transaction):
            # All Firestore reads precede any writes; required for real transactions.
            previous = _get(transaction, operation)
            room = _get(transaction, doc)
            if room is None:
                raise StoreError(404, "Not found")
            if action == "join":
                if uid not in room["seats"] and room["status"] != "lobby":
                    raise StoreError(409, "Room is no longer open")
            elif action in {"start", "settle", "score_adjust", "preset"}:
                _member(room, uid, admin=True, owner=owner)
                if not owner and room["admin_uid"] != uid:
                    raise StoreError(403, "Room admin required")
            else:
                _member(room, uid)
            if previous:
                if previous.get("fingerprint") != identity:
                    raise StoreError(409, "Conflicting idempotency key")
                return previous["response"]
            if room["version"] != expected_version:
                raise StoreError(409, "Stale room version")
            state_record = _get(transaction, private)
            if state_record is None:
                raise StoreError(503, "Game state unavailable")
            game_data = state_record.get("game")
            game = decode(game_data) if game_data is not None else None
            score = decode(state_record["score"])
            if not isinstance(score, ScoreState):
                raise StoreError(503, "Scoring state unavailable")
            controls = state_record.get("controls") or fresh()
            now = self.now_ms()
            auto_events = []
            # Reconcile timers at the same authoritative timestamp as this write.
            if room["status"] == "playing":
                try:
                    score, auto_events = reconcile(controls, game, score, now, room.get("game_id"))
                except ControlError as exc:
                    raise StoreError(exc.status, exc.detail) from exc
            event_data = {}
            if action == "join":
                if uid in room["seats"]:
                    return {
                        "room_id": room_id,
                        "version": room["version"],
                        "my_seat": room["seats"].index(uid),
                        "status": room["status"],
                    }
                seat = room["seats"].index(None) if None in room["seats"] else None
                if seat is None:
                    raise StoreError(409, "Room full")
                room["seats"][seat] = uid
                controls["presence"][seat] = now
                event_data = {"seat": seat}
            elif action == "start":
                if room["status"] not in ("lobby", "between") or None in room["seats"]:
                    raise StoreError(409, "Room is not ready")
                if score.closed:
                    raise StoreError(409, "Game is already closed")
                dealer = 2 if room["dealer"] is None else (room["dealer"] + 1) % 3
                game = start_game(deal(shuffled_deck(), dealer), score.passout_level)
                room["dealer"] = dealer
                room["game_id"] = uuid.uuid4().hex
                room["status"] = "playing"
                room.setdefault("started_at_ms", now)
                controls["timer"] = None
                controls["vote"] = None
                controls["candidate"] = None
                event_data = {"dealer": dealer, "game_id": room["game_id"]}
            elif action == "settle":
                if room["status"] != "awaiting_settlement" or not isinstance(game, GameState):
                    raise StoreError(409, "No completed deal to settle")
                if set(args) != {"regular_route", "passout_routes"}:
                    raise StoreError(422, "Invalid settlement options")
                try:
                    routes = tuple(RewardRoute(x) for x in args["passout_routes"])
                    score = settle_game(
                        score,
                        game,
                        room["game_id"],
                        regular_route=RewardRoute(args["regular_route"]),
                        passout_routes=routes,
                        expected_version=score.version,
                    )
                except (RuleViolation, ValueError, TypeError) as exc:
                    raise StoreError(422, "Invalid settlement") from exc
                room["status"] = "closed" if score.closed else "between"
                controls["candidate"] = None
                controls["timer"] = None
                event_data = {"score_version": score.version, "closed": score.closed}
                if score.closed:
                    # Final result and all ranking projections commit with the CLOSED room.
                    # No reads may occur after the first Firestore transaction write.
                    result_doc = self.db.collection("preferans_results").document(room_id)
                    if _get(transaction, result_doc) is not None:
                        raise StoreError(409, "Finished result already exists")
                    try:
                        final = final_result(room, score, now)
                        ranking_docs = [
                            self.db.collection("preferans_rankings").document(player["id"])
                            for player in final["players"]
                        ]
                        rankings = [
                            update_ranking(_get(transaction, ref), player, final)
                            for ref, player in zip(ranking_docs, final["players"])
                        ]
                    except (ValueError, TypeError, KeyError) as exc:
                        raise StoreError(503, "Invalid final accounting") from exc
            elif action == "preset":
                if room["status"] != "lobby":
                    raise StoreError(409, "Presets must be set before the first deal")
                try:
                    event_data = configure_policy(controls, args)
                except ControlError as exc:
                    raise StoreError(exc.status, exc.detail) from exc
            elif action == "score_adjust":
                if room["status"] not in ("playing", "between", "awaiting_settlement"):
                    raise StoreError(409, "Finished games cannot be edited")
                if uid != room["admin_uid"] and not owner:
                    raise StoreError(403, "Room admin required")
                if set(args) != {"field", "seat", "against", "delta", "reason"}:
                    raise StoreError(422, "Invalid adjustment")
                try:
                    score, event_data = adjust_score(
                        score,
                        controls,
                        args["field"],
                        args["seat"],
                        args["against"],
                        args["delta"],
                        args["reason"],
                        room["seats"].index(uid) if uid in room["seats"] else None,
                        now,
                        room.get("game_id") or "between",
                        room["version"] + 1,
                    )
                except ControlError as exc:
                    raise StoreError(exc.status, exc.detail) from exc
            else:
                if room["status"] != "playing" or not isinstance(game, GameState):
                    raise StoreError(409, "No active deal")
                seat = room["seats"].index(uid)
                try:
                    if action == "pulse":
                        if args:
                            raise ControlError(422, "Unexpected pulse arguments")
                        event_data = pulse(controls, seat, now)
                    elif action == "counter_start":
                        if args:
                            raise ControlError(422, "Unexpected counter arguments")
                        if not can_start_counter(controls, now):
                            raise ControlError(409, "Other players are not online")
                        event_data = start_counter(controls, game, score, seat, now)
                    elif action == "undo_request":
                        if set(args) != {"reason"}:
                            raise ControlError(422, "Undo requires a reason")
                        event_data = request_undo(
                            controls, seat, room["version"], now, args["reason"]
                        )
                    elif action == "undo_vote":
                        if set(args) != {"approve"}:
                            raise ControlError(422, "Undo vote requires approve")
                        game_restored, event_data = vote_undo(controls, seat, args["approve"], now)
                        if game_restored is not None:
                            game = game_restored
                    else:
                        if controls.get("paused_at") is not None or controls.get("vote"):
                            raise ControlError(409, "Game is paused for a vote or connection")
                        before = game
                        game = apply_command(game, seat, action, args)
                        event_data = redacted_action(action, args)
                        record_candidate(
                            controls,
                            before,
                            game,
                            action,
                            seat,
                            room["version"] + 1 + len(auto_events),
                        )
                        if controls.get("timer") is not None:
                            stop_counter(controls)
                        if game.phase == Phase.FINISHED:
                            room["status"] = "awaiting_settlement"
                except ControlError as exc:
                    raise StoreError(exc.status, exc.detail) from exc
                except (ValueError, TypeError, KeyError) as exc:
                    raise StoreError(422, "Illegal game action") from exc
            # Automatic timeout events are sequenced before the user mutation.
            for automatic in auto_events:
                room["version"] += 1
                sequence = room["version"]
                transaction.create(
                    doc.collection("events").document(f"{sequence:08d}"),
                    {"sequence": sequence, "seat": None, **automatic},
                )
            room["version"] += 1
            v = room["version"]
            event = {
                "sequence": v,
                "seat": room["seats"].index(uid) if uid in room["seats"] else None,
                "action": action,
                "data": event_data,
            }
            response = {"room_id": room_id, "version": v, "status": room["status"]}
            if action == "settle" and score.closed:
                transaction.create(result_doc, final)
                for ranking_doc, projection in zip(ranking_docs, rankings):
                    transaction.set(ranking_doc, projection)
            transaction.set(doc, room)
            transaction.set(
                private,
                {"game": encode(game), "score": encode(score), "controls": controls, "version": v},
            )
            transaction.create(doc.collection("events").document(f"{v:08d}"), event)
            transaction.create(operation, {"fingerprint": identity, "response": response})
            return response

        return commit(tx)

    def view(
        self, room_id: str, uid: str, *, owner: bool = False, since_version: int | None = None
    ) -> dict:
        if since_version is not None and (type(since_version) is not int or since_version < 0):
            raise StoreError(422, "Invalid version")
        doc = self._room(room_id)
        for _ in range(3):
            snap = doc.get(timeout=5.0)
            room = snap.to_dict() if snap.exists else None
            if room is None:
                raise StoreError(404, "Not found")
            _member(room, uid, admin=True, owner=owner)
            if uid not in room["seats"] and not owner:
                raise StoreError(404, "Not found")
            if since_version == room["version"]:
                return {"room_id": room_id, "version": room["version"], "unchanged": True}
            state = doc.collection("private").document("current").get(timeout=5.0)
            if not state.exists:
                raise StoreError(503, "Game state unavailable")
            state_data = state.to_dict()
            # Strongly coordinated versions prevent mixing two transactions in a view.
            if state_data.get("version") != room["version"]:
                continue
            game = decode(state_data["game"]) if state_data["game"] is not None else None
            score = decode(state_data["score"])
            if game is not None and not isinstance(game, GameState):
                raise StoreError(503, "Game state corrupted")
            return seat_view(
                room,
                game,
                score,
                uid,
                room["version"],
                owner=owner,
                controls=state_data.get("controls"),
                now_ms=self.now_ms(),
            )
        raise StoreError(409, "Room updated during read; retry")

    def events(self, room_id: str, uid: str, limit: int = 30, *, owner: bool = False) -> dict:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise StoreError(422, "Invalid history limit")
        doc = self._room(room_id)
        snap = doc.get(timeout=5.0)
        room = snap.to_dict() if snap.exists else None
        if room is None:
            raise StoreError(404, "Not found")
        _member(room, uid, admin=True, owner=owner)
        if uid not in room["seats"] and not owner:
            raise StoreError(404, "Not found")
        rows = doc.collection("events").order_by("sequence", direction="DESCENDING").limit(limit)
        return {
            "room_id": room_id,
            "version": room["version"],
            "events": [snap.to_dict() for snap in rows.stream(timeout=5.0)],
        }

    def invitation(self, room_id: str, uid: str) -> dict:
        """Opaque invitation envelope. No room UID, hand or game state is read."""
        if not isinstance(uid, str) or not uid or "/" in uid:
            raise StoreError(403, "Access denied")
        doc = self._room(room_id)
        snap = doc.get(timeout=5.0)
        room = snap.to_dict() if snap.exists else None
        if not isinstance(room, dict) or room.get("status") != "lobby":
            raise StoreError(404, "Not found")
        seats = room.get("seats")
        version = room.get("version")
        if (
            not isinstance(seats, list)
            or len(seats) != 3
            or any(seat is not None and not isinstance(seat, str) for seat in seats)
            or type(version) is not int
            or version < 0
        ):
            raise StoreError(503, "Room unavailable")
        return {
            "room_id": room_id,
            "version": version,
            "status": "lobby",
            "occupied": [seat is not None for seat in seats],
        }

    def history(self, uid: str, limit: int = 50) -> dict:
        """Only project-authorized callers can reach this method through the host guard."""
        if not isinstance(uid, str) or not uid or "/" in uid:
            raise StoreError(403, "Access denied")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise StoreError(422, "Invalid history limit")
        query = (
            self.db.collection("preferans_results")
            .order_by("finished_at_ms", direction="DESCENDING")
            .limit(limit + 1)
        )
        snapshots = [snap.to_dict() for snap in query.stream(timeout=5.0)]
        return {"results": snapshots[:limit], "has_more": len(snapshots) > limit, "limit": limit}

    def rankings(self, uid: str) -> dict:
        """Materialized across ALL completed games; never derive from a page."""
        if not isinstance(uid, str) or not uid or "/" in uid:
            raise StoreError(403, "Access denied")
        # This project is a private trio. Never accidentally serve a partial ranking.
        query = (
            self.db.collection("preferans_rankings")
            .order_by("gold", direction="DESCENDING")
            .limit(1001)
        )
        rows = [snap.to_dict() for snap in query.stream(timeout=5.0)]
        if len(rows) > 1000:
            raise StoreError(503, "Ranking exceeds supported size")
        rows.sort(key=lambda row: (-row["gold"], -row["net_vists"], row["id"]))
        return {"rankings": rows, "total_players": len(rows)}

    def result(self, room_id: str, uid: str) -> dict:
        if not isinstance(uid, str) or not uid or "/" in uid:
            raise StoreError(403, "Access denied")
        snapshot = (
            self.db.collection("preferans_results")
            .document(room_id if ROOM_ID.fullmatch(room_id) else "invalid")
            .get(timeout=5.0)
        )
        if not ROOM_ID.fullmatch(room_id) or not snapshot.exists:
            raise StoreError(404, "Not found")
        return snapshot.to_dict()
