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
from contextlib import nullcontext
from dataclasses import dataclass, replace
from typing import Any

from preferans.domain.auction import RuleViolation
from preferans.domain.cards import deal, shuffled_deck
from preferans.domain.game import EndReason, GameState, Phase, start_game
from preferans.domain.history import final_result, update_ranking
from preferans.domain.ledger import ScoreState
from preferans.domain.scoring import RewardRoute, settle_game
from preferans.online.codec import decode, encode
from preferans.online.commands import apply_command, redacted_action
from preferans.online import discard_gag
from preferans.online.controls import (
    ControlError,
    acting_seat,
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
    tick_controls,
    vote_undo,
)
from preferans.online.deal_flow import due as next_deal_due, schedule as schedule_next_deal
from preferans.online.views import public_bid, seat_view
from preferans.online.table_experience import THEMES, mark_activity, settlement_options
from preferans.online.table_presentation import remember_deal, room_day
from preferans.online.seat_swap import (
    ACTIONS as SWAP_ACTIONS,
    SeatSwapError,
    change as change_swap,
    pending as pending_swap,
)
from preferans.online.presentation import (
    ACTIONS as PRESENTATION_ACTIONS,
    PresentationError,
    allows_replay_move,
    change as change_presentation,
    close_after_move,
    invalidate_ready,
)
from preferans.online.pause_clock import synchronize
from preferans.online.sheet_exit import (
    ACTIONS as SHEET_ACTIONS,
    SheetExitError,
    change as change_sheet,
    finish as finish_sheet,
)
from preferans.online.realtime import CHECKPOINT_MS, HubError, enabled as realtime_enabled, hub

from preferans.online import punch_choices, ruleset_catalog
from preferans.online.pause_clock import retire_reveal

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
    # Transaction.get(ref) yields snapshots; DocumentReference.get returns one.
    # Keep the read inside this transaction and before every staged write.
    snap = ref.get(transaction=tx, timeout=5.0)
    return snap.to_dict() if snap.exists else None


def _begin_deal(room: dict, score: ScoreState, controls: dict, now: int, dealer: int):
    previous_game_id = room.get("game_id")
    previous = controls.get("score_sheet_deals", {}).get(previous_game_id, {})
    controls["previous_passout"] = previous.get("passout")
    game = start_game(deal(shuffled_deck(), dealer), score.passout_level)
    room["dealer"] = dealer
    room["game_id"] = uuid.uuid4().hex
    room["status"] = "playing"
    room.setdefault("started_at_ms", now)
    controls["timer"] = None
    controls["vote"] = None
    controls["candidate"] = None
    controls.pop("next_deal", None)
    controls.pop("sheet_offers", None)
    controls.pop("passout_choices", None)
    controls.pop("reveal", None)
    controls.pop("revealed_cards", None)
    mark_activity(room, game, now)
    if discard_gag.begin(controls, previous_game_id, room["game_id"], now):
        room["activity_started_at_ms"] = now + discard_gag.GAG_TOTAL_MS
    return game


def _after_settlement(room, score, controls, now, use_rt, game):
    """One transition for regular settlement and an accepted misere."""
    remember_deal(controls, room["game_id"], game)
    if score.closed:
        room["status"] = "awaiting_settlement"
        room["final_review"] = True
        finish_sheet(controls)
        controls.pop("reveal", None)
        controls.pop("revealed_cards", None)
        controls.pop("passout_choices", None)
    else:
        room["status"] = "between"
        controls.pop("next_deal", None)
        if use_rt:
            schedule_next_deal(controls, room["game_id"], now)
        controls["candidate"] = None
        controls["timer"] = None


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

    def create(self, uid: str, token: str, *, require_ready: bool = False) -> dict:
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
            created = self.now_ms()
            day = room_day(created)
            daily_ref = self.db.collection("preferans_room_days").document(day)
            daily = _get(transaction, daily_ref) or {"last": 0}
            number = daily["last"] + 1
            room = {
                "day": day,
                "daily_number": number,
                "id": room_id,
                "admin_uid": uid,
                "seats": [uid, None, None],
                "status": "lobby",
                "version": 0,
                "game_id": None,
                "dealer": None,
                "created_at_ms": created,
            }
            if require_ready:
                room["lobby_setup"] = {"ready": [False, False, False], "dealer": 2}
            result = {"room_id": room_id, "version": 0, "my_seat": 0, "status": "lobby"}
            transaction.create(doc, room)
            transaction.set(daily_ref, {"last": number})
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
        self,
        room_id: str,
        uid: str,
        token: str,
        expected_version: int,
        action: str,
        args: dict,
        owner: bool = False,
    ) -> dict:
        if action in {"sheet_offer", "sheet_reply"}:
            raise StoreError(422, "Sheet proposals are no longer supported")
        if realtime_enabled() and action == "pulse":
            if args:
                raise StoreError(422, "Unexpected pulse arguments")
            return self.realtime_pulse(room_id, uid)
        return self._mutate(room_id, uid, token, expected_version, action, args, owner)

    def settle(
        self, room_id: str, uid: str, token: str, expected_version: int, args: dict, owner: bool
    ) -> dict:
        return self._mutate(room_id, uid, token, expected_version, "settle", args, owner)

    def admin_adjust(
        self, room_id: str, uid: str, token: str, expected_version: int, args: dict, owner: bool
    ) -> dict:
        return self._mutate(room_id, uid, token, expected_version, "score_adjust", args, owner)

    def _realtime_controls(self, room, controls, game, score, now):
        # Read presence + loss generation atomically. This is process-local, not a DB read.
        with hub.lock:
            presence = hub.presence(room["id"], room["seats"], now)
            generation, interrupted = hub.generation(room["id"])
        restarted = controls.get("rt_epoch") != hub.epoch
        retired = retire_reveal(controls, now)
        events = synchronize(controls, presence, hub.epoch, now, interrupted=interrupted)
        if retired:
            events.append({"action": "legacy_reveal_retired", "data": {}})
        events.extend(invalidate_ready(controls, presence, restarted or interrupted))
        if room["status"] == "playing":
            score, expired = tick_controls(controls, game, score, now, room.get("game_id"))
            events.extend(expired)
        return score, events, generation

    def _publish_realtime(self, room, game, score, controls, now, generation):
        # Only after commit success, never inside the retryable transaction body.
        # Publication failure must not change an already committed HTTP result.
        import os

        try:
            owner_uid = os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
            views = {
                uid: seat_view(
                    room,
                    game,
                    score,
                    uid,
                    room["version"],
                    owner=uid == owner_uid,
                    controls=controls,
                    now_ms=now,
                )
                for uid in room["seats"]
                if uid
            }
            hub.publish(room["id"], views, now)
            hub.handled(room["id"], generation)
        except Exception:
            # Next authenticated view/revalidation can recover. No private state logged.
            return

    def realtime_pulse(self, room_id: str, uid: str) -> dict:
        # Legacy HTTP fallback acknowledges presence, not an ordinary game mutation.
        # The host still checks identity/grant on every request.
        with hub.commit_lock:
            view = self.view(room_id, uid)
            if view.get("my_seat") is None:
                raise StoreError(403, "Seat required")
            now = self.now_ms()
            try:
                hub.fallback(room_id, uid, view, now)
            except HubError as exc:
                raise StoreError(503, "Realtime unavailable") from exc
            if hub.due(room_id, now):
                signature = tuple(s == "online" for s in hub.statuses(room_id, now))
                ok = False
                try:
                    result = self.sync_realtime(room_id, uid)
                    ok = True
                finally:
                    hub.synced(room_id, self.now_ms(), ok, signature)
                return result
            return {"room_id": room_id, "version": view["version"], "status": view["status"]}

    def sync_realtime(self, room_id: str, uid: str) -> dict:
        """Persist only meaningful pause/clock transitions or rare active-clock checkpoints."""
        doc = self._room(room_id)
        private = doc.collection("private").document("current")
        tx = self.db.transaction()
        captured = None
        observed_generation = 0

        @self.fs.transactional
        def commit(transaction):
            nonlocal captured, observed_generation
            captured = None
            observed_generation, _ = hub.generation(room_id)
            with hub.lock:
                hub.metrics["sync_reads"] += 1
            room = _get(transaction, doc)
            if room is None:
                raise StoreError(404, "Not found")
            _member(room, uid)
            result = {"room_id": room_id, "version": room["version"], "status": room["status"]}
            if room.get("final_review") or room["status"] not in {
                "playing",
                "between",
                "awaiting_settlement",
            }:
                return result
            with hub.lock:
                hub.metrics["sync_reads"] += 1
            record = _get(transaction, private)
            if record is None or record.get("version") != room["version"]:
                raise StoreError(503, "Game state unavailable")
            game = decode(record["game"]) if record["game"] is not None else None
            score = decode(record["score"])
            if not isinstance(score, ScoreState):
                raise StoreError(503, "Scoring state unavailable")
            controls = record.get("controls") or fresh()
            now = self.now_ms()
            last = controls.get("rt_checkpoint_ms")
            try:
                score, events, generation = self._realtime_controls(
                    room, controls, game, score, now
                )
            except ControlError as exc:
                raise StoreError(exc.status, exc.detail) from exc
            # The existing single-worker reconciliation loop is the scheduler.
            # No client clock, background billable job or extra polling is needed.
            if (
                room["status"] == "between"
                and isinstance(game, GameState)
                and game.phase == Phase.FINISHED
                and not score.closed
                and None not in room["seats"]
                and next_deal_due(controls, room.get("game_id"), now)
            ):
                dealer = (room["dealer"] + 1) % 3
                game = _begin_deal(room, score, controls, now, dealer)
                events.append(
                    {
                        "action": "start",
                        "data": {"dealer": dealer, "game_id": room["game_id"], "automatic": True},
                    }
                )
                result["status"] = room["status"]
            active_clock = any(
                isinstance((controls.get(key) or {}).get("deadline_ms"), int)
                for key in ("timer", "vote")
            )
            checkpoint = active_clock and (not isinstance(last, int) or now - last >= CHECKPOINT_MS)
            writes = 0
            for event in events:
                room["version"] += 1
                sequence = room["version"]
                transaction.create(
                    doc.collection("events").document(f"{sequence:08d}"),
                    {"sequence": sequence, "seat": None, **event},
                )
                writes += 1
            if events:
                transaction.set(doc, room)
                writes += 1
            if events or checkpoint:
                transaction.set(
                    private,
                    {
                        "game": encode(game),
                        "score": encode(score),
                        "controls": controls,
                        "version": room["version"],
                    },
                )
                writes += 1
            with hub.lock:
                hub.metrics["sync_writes"] += writes
            captured = (room, game, score, controls, now, generation)
            result["version"] = room["version"]
            return result

        with hub.commit_lock:
            result = commit(tx)
            if captured is not None:
                self._publish_realtime(*captured)
            else:
                hub.handled(room_id, observed_generation)
            return result

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
        if action in {"reveal_report", "reveal_propose", "reveal_vote"}:
            raise StoreError(422, "Accidental disclosure actions are retired")
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
        use_rt = realtime_enabled()
        captured = None
        generation = 0
        swapped = False

        @self.fs.transactional
        def commit(transaction):
            nonlocal captured, generation, swapped
            captured = None
            generation = 0
            swapped = False
            # All Firestore reads precede any writes; required for real transactions.
            previous = _get(transaction, operation)
            room = _get(transaction, doc)
            if room is None:
                raise StoreError(404, "Not found")
            if action == "join":
                if uid not in room["seats"] and room["status"] != "lobby":
                    raise StoreError(409, "Room is no longer open")
            elif action == "archive":
                if not owner:
                    raise StoreError(403, "Owner required")
            elif action == "start":
                _member(room, uid, admin=True, owner=owner)
                setup = room.get("lobby_setup") if room["status"] == "lobby" else None
                dealer = setup.get("dealer") if setup else None
                if room["status"] == "between" and type(room.get("dealer")) is int:
                    dealer = (room["dealer"] + 1) % 3
                selected = (
                    type(dealer) is int and dealer in range(3) and room["seats"][dealer] == uid
                )
                replay = (
                    previous and previous.get("fingerprint") == identity and uid in room["seats"]
                )
                if not owner and room["admin_uid"] != uid and not selected and not replay:
                    raise StoreError(403, "Room admin or selected dealer required")
            elif action == "settle":
                _member(room, uid, admin=True, owner=owner)
            elif action in {
                "score_adjust",
                "final_confirm",
                "preset",
                "lobby_config",
                "ruleset_select",
                "table_theme",
            }:
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
            if room["status"] == "archived":
                raise StoreError(409, "Archived room is read-only")
            state_record = _get(transaction, private)
            if state_record is None:
                raise StoreError(503, "Game state unavailable")
            game_data = state_record.get("game")
            game = decode(game_data) if game_data is not None else None
            score = decode(state_record["score"])
            if not isinstance(score, ScoreState):
                raise StoreError(503, "Scoring state unavailable")
            controls = state_record.get("controls") or fresh()
            review = room["status"] == "awaiting_settlement" and score.closed
            if review and action not in {"score_adjust", "final_confirm"}:
                raise StoreError(409, "Confirm or correct the final settlement first")
            now = self.now_ms()
            retire_reveal(controls, now)
            auto_events = []
            # Reconcile timers at the same authoritative timestamp as this write.
            if review or action in SHEET_ACTIONS or action == "archive":
                # A voluntary exit must remain possible during any pause. No
                # implicit settlement or timer penalty is charged by this action.
                pass
            elif use_rt and room["status"] in {"playing", "between", "awaiting_settlement"}:
                try:
                    score, auto_events, generation = self._realtime_controls(
                        room, controls, game, score, now
                    )
                except ControlError as exc:
                    raise StoreError(exc.status, exc.detail) from exc
                if (
                    controls.get("paused_at") is not None
                    and action not in {"score_adjust"}
                    and action not in PRESENTATION_ACTIONS
                    and not (action == "play" and allows_replay_move(controls))
                ):
                    raise StoreError(409, "Game is paused for a connection or shared reason")
            elif room["status"] == "playing":
                try:
                    score, auto_events = reconcile(controls, game, score, now, room.get("game_id"))
                except ControlError as exc:
                    raise StoreError(exc.status, exc.detail) from exc
            if (
                isinstance(game, GameState)
                and game.claim_pending
                and action not in {"claim_vote", "pulse", "sheet_discard", "archive"}
            ):
                raise StoreError(409, "Resolve the remaining-tricks offer first")
            event_data = {}
            sheet_loser = None
            choice_update = None
            choice_rankings = []
            choice_ref = None
            seat_before = room["seats"].index(uid) if uid in room["seats"] else None
            if pending_swap(room) and action in {
                "dealer_pass",
                "start",
                "lobby_ready",
                "lobby_config",
                "preset",
                "ruleset_select",
            }:
                raise StoreError(409, "Resolve seat change first")
            if action == "final_confirm":
                if not review or args:
                    raise StoreError(409, "No final settlement awaiting confirmation")
                room["status"] = "closed"
                room.pop("final_review", None)
                event_data = {"score_version": score.version}
            elif action == "archive":
                reason = args.get("reason")
                if (
                    set(args) != {"reason"}
                    or not isinstance(reason, str)
                    or not 5 <= len(reason.strip()) <= 180
                    or any(ord(ch) < 32 or ord(ch) == 127 for ch in reason)
                ):
                    raise StoreError(422, "Archive requires a reason")
                if (
                    room["status"] not in {"lobby", "playing", "between", "awaiting_settlement"}
                    or score.closed
                ):
                    raise StoreError(409, "Only unfinished rooms may be archived")
                if (
                    _get(transaction, self.db.collection("preferans_results").document(room_id))
                    is not None
                ):
                    raise StoreError(409, "Result already exists")
                room["status"] = "archived"
                room["archived_at_ms"] = now
                room.pop("seat_swap", None)
                finish_sheet(controls)
                controls.pop("reveal", None)
                controls.pop("revealed_cards", None)
                event_data = {"reason": reason.strip(), "archived_at_ms": now}
            elif action == "punch_choose":
                if (
                    room["status"] != "closed"
                    or room.get("sheet_loser") is not None
                    or not room.get("punch_choices")
                ):
                    raise StoreError(409, "No eligible completed result")
                try:
                    event_data, count = punch_choices.choose(
                        room["punch_choices"], seat_before, args
                    )
                    result_ref = self.db.collection("preferans_results").document(room_id)
                    original = _get(transaction, result_ref)
                    if not original or original["reason"] != "pool_closed":
                        raise ValueError("Immutable result unavailable")
                    choice_ref = self.db.collection("preferans_punch_choices").document(room_id)
                    choice_update = {"pairs": room["punch_choices"]}
                    if count:
                        for actor, side in (
                            (event_data["from"], "given"),
                            (seat_before, "received"),
                        ):
                            player = next(p for p in original["players"] if p["seat"] == actor)
                            ref = self.db.collection("preferans_rankings").document(player["id"])
                            ranking = _get(transaction, ref)
                            if not ranking or ranking.get("id") != player["id"]:
                                raise ValueError("Ranking unavailable")
                            choice_rankings.append(
                                (ref, punch_choices.ranking_delta(ranking, side, count))
                            )
                except (ValueError, KeyError, TypeError, StopIteration) as exc:
                    raise StoreError(409, "Invalid or already recorded punishment choice") from exc
            elif action == "ruleset_select":
                if (
                    room["status"] != "lobby"
                    or game is not None
                    or score.version != 0
                    or "lobby_setup" not in room
                ):
                    raise StoreError(409, "Select rules before the first deal")
                if set(args) != {"id", "version"}:
                    raise StoreError(422, "Invalid ruleset selection")
                try:
                    template = ruleset_catalog.load(
                        transaction, self.db, args["id"], args["version"]
                    )
                    rules, policy = ruleset_catalog.validated(
                        template["id"],
                        template["version"],
                        template["parameters"],
                        template["policy"],
                    )
                    if (
                        rules.fingerprint() != template["sha256"]
                        or ruleset_catalog.snapshot_hash(rules, policy) != template["snapshot_hash"]
                    ):
                        raise ValueError("Template hash mismatch")
                    if not 2 <= rules.pool_target <= 40 or rules.pool_target % 2:
                        raise ValueError("Room pool target must be even and between 2 and 40")
                    score = ScoreState.new(rules)
                    controls["policy"] = policy
                except (ValueError, TypeError, KeyError) as exc:
                    raise StoreError(422, "Invalid template revision") from exc
                room["ruleset_name"] = template["name"]
                room["lobby_setup"]["ready"] = [False, False, False]
                event_data = {
                    "id": template["id"],
                    "version": template["version"],
                    "sha256": template["sha256"],
                }
            elif action in SWAP_ACTIONS:
                if game is not None or score.version != 0:
                    raise StoreError(409, "Seat changes require an untouched game")
                try:
                    event_data, swapped = change_swap(
                        control=controls, room=room, seat=seat_before, action=action, args=args
                    )
                except SeatSwapError as exc:
                    raise StoreError(exc.code, str(exc)) from exc
            elif action in SHEET_ACTIONS:
                try:
                    event_data, sheet_loser = change_sheet(
                        controls, room, room["seats"].index(uid), action, args
                    )
                except SheetExitError as exc:
                    raise StoreError(exc.code, str(exc)) from exc
                if sheet_loser is not None:
                    room["status"] = "closed"
                    room["sheet_loser"] = sheet_loser
                    finish_sheet(controls)
                    controls.pop("reveal", None)
                    controls.pop("revealed_cards", None)
            elif action in PRESENTATION_ACTIONS:
                # The shared pause API uses the existing authenticated transaction.
                # New shared actions need the realtime presence scheduler. On rollback
                # permit closing an already-open overlay, never force-resume a break.
                if not use_rt and action != "overlay_close":
                    raise StoreError(409, "Shared room requires realtime")
                try:
                    event_data = change_presentation(
                        controls, room, game, room["seats"].index(uid), action, args, now
                    )
                except PresentationError as exc:
                    raise StoreError(exc.code, str(exc)) from exc
            elif action == "join":
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
                if "lobby_setup" in room:
                    room["lobby_setup"]["ready"] = [False, False, False]
                controls["presence"][seat] = now
                event_data = {"seat": seat}
            elif action == "start":
                if room["status"] not in ("lobby", "between") or None in room["seats"]:
                    raise StoreError(409, "Room is not ready")
                if score.closed:
                    raise StoreError(409, "Game is already closed")
                if room["status"] == "lobby" and (not 2 <= score.target <= 40 or score.target % 2):
                    raise StoreError(422, "Room pool target must be even and between 2 and 40")
                if (
                    use_rt
                    and room["status"] == "between"
                    and controls.get("next_deal")
                    and not next_deal_due(controls, room.get("game_id"), now)
                ):
                    raise StoreError(409, "Next deal is not due")
                setup = room.get("lobby_setup") if room["status"] == "lobby" else None
                if setup is not None and setup.get("ready") != [True, True, True]:
                    raise StoreError(409, "All three players must confirm the setup")
                dealer = (
                    (setup["dealer"] if setup is not None else 2)
                    if room["dealer"] is None
                    else (room["dealer"] + 1) % 3
                )
                game = _begin_deal(room, score, controls, now, dealer)
                event_data = {"dealer": dealer, "game_id": room["game_id"]}
                if use_rt:
                    score, events, generation = self._realtime_controls(
                        room, controls, game, score, now
                    )
                    auto_events.extend(events)
            elif action == "passout_reward":
                if (
                    room["status"] != "awaiting_settlement"
                    or not isinstance(game, GameState)
                    or not game.is_passout
                ):
                    raise StoreError(409, "No passout reward choice")
                seat = room["seats"].index(uid)
                selected = controls.setdefault("passout_choices", {})
                options = settlement_options(score, game, selected)
                if (
                    set(args) != {"route"}
                    or seat not in options["passout_pending"]
                    or args["route"] not in options["passout_choices"][seat]
                ):
                    raise StoreError(422, "Invalid or already submitted reward choice")
                selected[str(seat)] = args["route"]
                event_data = {"seat": seat, "route": args["route"]}
            elif action == "settle":
                if room["status"] != "awaiting_settlement" or not isinstance(game, GameState):
                    raise StoreError(409, "No completed deal to settle")
                if not owner and room["admin_uid"] != uid:
                    if (
                        game.declarer != room["seats"].index(uid)
                        or not settlement_options(score, game)["regular_choice"]
                    ):
                        raise StoreError(
                            403, "Room admin or declarer with settlement choice required"
                        )
                if controls.get("vote"):
                    raise StoreError(409, "Pending undo decision")
                if set(args) != {"regular_route", "passout_routes"}:
                    raise StoreError(422, "Invalid settlement options")
                options = settlement_options(score, game, controls.get("passout_choices"))
                if options.get("passout_pending"):
                    raise StoreError(409, "Awaiting player reward decisions")
                if (
                    game.is_passout
                    and any(options.get("passout_choices", []))
                    and (
                        not isinstance(args["passout_routes"], (list, tuple))
                        or list(args["passout_routes"]) != options["passout_defaults"]
                    )
                ):
                    raise StoreError(422, "Settlement must use the players' confirmed choices")
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
                _after_settlement(room, score, controls, now, use_rt, game)
                event_data = {"score_version": score.version, "closed": score.closed}
            elif action == "lobby_ready":
                if room["status"] != "lobby" or "lobby_setup" not in room or None in room["seats"]:
                    raise StoreError(409, "Lobby setup is not ready")
                if set(args) != {"ready"} or type(args["ready"]) is not bool:
                    raise StoreError(422, "Invalid readiness")
                seat = room["seats"].index(uid)
                room["lobby_setup"]["ready"][seat] = args["ready"]
                event_data = {"seat": seat, "ready": args["ready"]}
            elif action == "table_theme":
                theme = args.get("theme")
                if set(args) != {"theme"} or not isinstance(theme, str) or theme not in THEMES:
                    raise StoreError(422, "Invalid table theme")
                if room["status"] not in {"lobby", "playing", "between", "awaiting_settlement"}:
                    raise StoreError(409, "Table theme cannot change in a finished room")
                room["table_theme"] = theme
                event_data = {"theme": theme}
            elif action == "dealer_pass":
                setup = room.get("lobby_setup")
                if room["status"] != "lobby" or not setup or game is not None:
                    raise StoreError(409, "Dealer can only be passed before the first deal")
                seat = room["seats"].index(uid)
                if seat != setup["dealer"]:
                    raise StoreError(403, "Only the selected dealer may pass the deck")
                target = args.get("dealer")
                if (
                    set(args) != {"dealer"}
                    or type(target) is not int
                    or target not in range(3)
                    or target == seat
                    or room["seats"][target] is None
                ):
                    raise StoreError(422, "Invalid dealer target")
                setup["dealer"] = target
                setup["ready"] = [False, False, False]
                event_data = {"from": seat, "dealer": target}
            elif action == "lobby_config":
                if room["status"] != "lobby" or "lobby_setup" not in room:
                    raise StoreError(409, "Setup can only change before the first deal")
                if (
                    set(args) != {"dealer", "target"}
                    or type(args["dealer"]) is not int
                    or args["dealer"] not in range(3)
                    or type(args["target"]) is not int
                    or not 2 <= args["target"] <= 40
                    or args["target"] % 2 != 0
                ):
                    raise StoreError(422, "Invalid lobby setup")
                room["lobby_setup"] = {"ready": [False, False, False], "dealer": args["dealer"]}
                if args["target"] != score.target:
                    score = ScoreState.new(
                        replace(
                            score.ruleset.rules,
                            identifier="room-custom",
                            version=1,
                            pool_target=args["target"],
                        )
                    )
                    room.pop("ruleset_name", None)
                event_data = {"dealer": args["dealer"], "target": args["target"]}
            elif action == "preset":
                if room["status"] != "lobby":
                    raise StoreError(409, "Presets must be set before the first deal")
                try:
                    old_policy = controls.get("policy")
                    event_data = configure_policy(controls, args)
                    if controls["policy"] != old_policy:
                        score = ScoreState.new(
                            replace(score.ruleset.rules, identifier="room-custom", version=1)
                        )
                        room.pop("ruleset_name", None)
                    if "lobby_setup" in room:
                        room["lobby_setup"]["ready"] = [False, False, False]
                except ControlError as exc:
                    raise StoreError(exc.status, exc.detail) from exc
            elif action == "score_adjust":
                if room["status"] not in ("playing", "between", "awaiting_settlement"):
                    raise StoreError(409, "Finished games cannot be edited")
                if uid != room["admin_uid"] and not owner:
                    raise StoreError(403, "Room admin required")
                if set(args) != {"field", "seat", "against", "delta", "reason"}:
                    raise StoreError(422, "Invalid adjustment")
                if review and args["field"] == "pool":
                    raise StoreError(422, "Final review allows hill and vist corrections only")
                controls.pop("passout_choices", None)
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
                if action != "pulse" and discard_gag.active(controls, room.get("game_id"), now):
                    raise StoreError(409, "Wait for the redeal presentation")
                try:
                    if action == "pulse":
                        if args:
                            raise ControlError(422, "Unexpected pulse arguments")
                        event_data = pulse(controls, seat, now)
                    elif action == "counter_start":
                        if args and (
                            set(args) != {"target"}
                            or type(args["target"]) is not int
                            or args["target"] != acting_seat(game)
                        ):
                            raise ControlError(
                                422, "Counter target must be the current decision maker"
                            )
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
                        replay_move = action == "play" and allows_replay_move(controls)
                        if (
                            controls.get("paused_at") is not None and not replay_move
                        ) or controls.get("vote"):
                            raise ControlError(409, "Game is paused for a vote or connection")
                        before = game
                        game = apply_command(game, seat, action, args)
                        if action == "discard":
                            discard_gag.record_discard(
                                controls,
                                room["game_id"],
                                seat,
                                now,
                                args.get("hide_under_sheet") is True,
                            )
                        if replay_move:
                            close_after_move(controls, now)
                        event_data = redacted_action(action, args)
                        if action == "without_three":
                            event_data = {"bid": public_bid(game.contract)}
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
                            if game.end_reason in (
                                EndReason.MISERE_ACCEPTED,
                                EndReason.WITHOUT_THREE,
                            ):
                                # Unambiguous terminal outcomes settle in the same transaction.
                                # No defense phase, reward selection, or separate admin command.
                                score = settle_game(
                                    score, game, room["game_id"], expected_version=score.version
                                )
                                _after_settlement(room, score, controls, now, use_rt, game)
                                event_data = {
                                    **event_data,
                                    "score_version": score.version,
                                    "closed": score.closed,
                                }
                            else:
                                room["status"] = "awaiting_settlement"
                except ControlError as exc:
                    raise StoreError(exc.status, exc.detail) from exc
                except (ValueError, TypeError, KeyError) as exc:
                    raise StoreError(422, "Illegal game action") from exc
            finalize = (
                action == "final_confirm" and room["status"] == "closed" and score.closed
            ) or sheet_loser is not None
            if finalize:
                # All reads precede writes, including the immutable result and all rankings.
                result_doc = self.db.collection("preferans_results").document(room_id)
                if _get(transaction, result_doc) is not None:
                    raise StoreError(409, "Finished result already exists")
                try:
                    final = final_result(room, score, now, sheet_loser=sheet_loser)
                    final["ruleset_id"] = score.ruleset.rules.identifier
                    final["ruleset_policy"] = dict(controls.get("policy", {}))
                    final["ruleset_snapshot_hash"] = ruleset_catalog.snapshot_hash(
                        score.ruleset.rules, final["ruleset_policy"]
                    )
                    final["ruleset_snapshot"] = encode(score.ruleset)
                    if sheet_loser is None:
                        room["final_punches"] = [dict(award) for award in final["punches"]]
                        pairs = punch_choices.initial(final)
                        final["punches_confirmed"] = not pairs
                        if pairs:
                            room["punch_choices"] = pairs
                            choice_ref = self.db.collection("preferans_punch_choices").document(
                                room_id
                            )
                            choice_update = {"pairs": pairs}
                    else:
                        final["punches_confirmed"] = True
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
            # Automatic timeout events are sequenced before the user mutation.
            for automatic in auto_events:
                room["version"] += 1
                sequence = room["version"]
                transaction.create(
                    doc.collection("events").document(f"{sequence:08d}"),
                    {"sequence": sequence, "seat": None, **automatic},
                )
            mark_activity(room, game, now)
            room["version"] += 1
            v = room["version"]
            event = {
                "sequence": v,
                "seat": seat_before
                if action in SWAP_ACTIONS
                else (room["seats"].index(uid) if uid in room["seats"] else None),
                "action": action,
                "data": event_data,
            }
            response = {"room_id": room_id, "version": v, "status": room["status"]}
            if finalize:
                transaction.create(result_doc, final)
                for ranking_doc, projection in zip(ranking_docs, rankings):
                    transaction.set(ranking_doc, projection)
            if choice_ref is not None:
                transaction.set(choice_ref, choice_update)
                for ref, ranking in choice_rankings:
                    transaction.set(ref, ranking)
            transaction.set(doc, room)
            transaction.set(
                private,
                {"game": encode(game), "score": encode(score), "controls": controls, "version": v},
            )
            transaction.create(doc.collection("events").document(f"{v:08d}"), event)
            transaction.create(operation, {"fingerprint": identity, "response": response})
            if use_rt:
                captured = (room, game, score, controls, now, generation)
            return response

        with hub.commit_lock if use_rt else nullcontext():
            result = commit(tx)
            if captured is not None:
                with hub.lock:
                    hub.metrics["mutation_commits"] += 1
                    hub.metrics["mutation_min_reads"] += 3
                    hub.metrics["mutation_min_writes"] += 4
                if swapped:
                    hub.invalidate_seats(room_id, captured[4])
                self._publish_realtime(*captured)
            return result

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
        return {
            "results": [self._effective_result(row) for row in snapshots[:limit]],
            "has_more": len(snapshots) > limit,
            "limit": limit,
        }

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
        from preferans.online.history_names import ranking_names

        names = ranking_names(self.db, {row["id"] for row in rows})
        return {"rankings": rows, "total_players": len(rows), "player_names": names}

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
        return self._effective_result(snapshot.to_dict())

    def _effective_result(self, original: dict) -> dict:
        if original.get("reason") != "pool_closed" or not any(
            p["bare"] for p in original["punches"]
        ):
            return original
        snap = (
            self.db.collection("preferans_punch_choices")
            .document(original["room_id"])
            .get(timeout=5.0)
        )
        return (
            punch_choices.effective(original, snap.to_dict()["pairs"]) if snap.exists else original
        )
