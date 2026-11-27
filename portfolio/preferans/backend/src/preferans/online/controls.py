"""Deterministic room controls; the Firestore adapter owns transaction boundaries.

Private candidate snapshots NEVER enter a public projection or audit event.  Server
wall time is supplied by the host; clients cannot choose timer timestamps.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from preferans.domain.auction import BidKind, RuleViolation
from preferans.domain.game import GameState, Phase
from preferans.domain.ledger import EntryKind, LedgerEntry, ScoreState
from preferans.online.codec import decode, encode
from preferans.online.pause_clock import reasons, transition

TIMER_MS = 180_000
VOTE_MS = 120_000
HEARTBEAT_MS = 45_000
STALE_MS = 100_000
MAX_PERIODS_PER_SYNC = 100_000


class ControlError(ValueError):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def fresh() -> dict[str, Any]:
    return {
        "timer": None,
        "vote": None,
        "candidate": None,
        "paused_at": None,
        "presence": [None, None, None],
        "adjustments": [],
        "policy": {"counter_seconds": 180, "counter_multiplier": 3, "undo_seconds": 120},
    }


def _valid_seat(seat: int) -> int:
    if type(seat) is not int or seat not in (0, 1, 2):
        raise ControlError(422, "Invalid seat")
    return seat


def acting_seat(game: GameState) -> int | None:
    if game.claim_pending or game.phase == Phase.MISERE_OFFER:
        return None
    if game.phase in (Phase.PLAY, Phase.OPENING_LEAD):
        return game.controllers[game.turn] if game.turn is not None else None
    if game.phase in (Phase.DISCARD, Phase.DECLARE):
        return game.declarer
    return game.turn


def timer_cost(game: GameState, score: ScoreState) -> int:
    if game.is_passout:
        return score.ruleset.rules.passout_cost(game.passout_level)
    bid = game.contract or game.auction.high_bid
    if bid is None:
        return score.ruleset.rules.cost(game.passout_level)
    if bid.kind in (BidKind.MISERE, BidKind.MISERE_NO_WIDOW):
        return score.ruleset.rules.misere_cost
    if bid.level is None:
        raise RuleViolation("Contract level missing")
    return score.ruleset.rules.cost(bid.level)


def _text(value: object) -> str:
    if not isinstance(value, str) or not 5 <= len(value.strip()) <= 180:
        raise ControlError(422, "A reason of 5–180 characters is required")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ControlError(422, "Control characters in reason")
    return value.strip()


def record_candidate(
    control: dict, before: GameState, after: GameState, action: str, actor: int, version: int
) -> None:
    # Only the latest qualifying move can be undone; a complete trick cannot.
    eligible_card = (
        action == "play"
        and len(after.trick) > 0
        and after.phase in (Phase.PLAY, Phase.CHOOSE_MODE)
        and len(after.completed_tricks) == len(before.completed_tricks)
    )
    eligible_bid = (
        action in {"bid", "here"} and before.phase == Phase.AUCTION and after.phase == Phase.AUCTION
    )
    control["candidate"] = (
        {
            "kind": "card_play" if eligible_card else "auction_bid",
            "seat": actor,
            "version": version,
            "game": encode(before),
        }
        if eligible_card or eligible_bid
        else None
    )


def request_undo(control: dict, actor: int, version: int, now_ms: int, reason: object) -> dict:
    candidate = control.get("candidate")
    if control.get("paused_at") is not None:
        raise ControlError(409, "Game is paused")
    if control.get("vote") or not candidate or candidate["seat"] != actor:
        raise ControlError(409, "Only the author of the latest reversible move may request undo")
    note = _text(reason)
    timer = control.get("timer")
    if timer is not None:
        timer["remaining_ms"] = max(0, timer["deadline_ms"] - now_ms)
        timer["deadline_ms"] = None
    deadline = now_ms + control["policy"]["undo_seconds"] * 1000
    control["vote"] = {
        "kind": candidate["kind"],
        "requester": actor,
        "deadline_ms": deadline,
        "votes": {},
        "reason": note,
    }
    return {"kind": candidate["kind"], "requester": actor, "deadline_ms": deadline}


def vote_undo(
    control: dict, actor: int, approve: object, now_ms: int
) -> tuple[GameState | None, dict]:
    _valid_seat(actor)
    vote = control.get("vote")
    if not vote:
        raise ControlError(409, "No pending undo vote")
    if control.get("paused_at") is not None or vote.get("deadline_ms") is None:
        raise ControlError(409, "Undo vote is paused")
    if now_ms >= vote["deadline_ms"]:
        raise ControlError(409, "Undo vote expired")
    if actor == vote["requester"] or str(actor) in vote["votes"] or type(approve) is not bool:
        raise ControlError(422, "Invalid or duplicate vote")
    vote["votes"][str(actor)] = approve
    event = {"kind": vote["kind"], "voter": actor, "approved": approve}
    if not approve:
        _end_vote(control, now_ms)
        event["outcome"] = "rejected"
        return None, event
    if len(vote["votes"]) != 2:
        event["outcome"] = "pending"
        return None, event
    candidate = control["candidate"]
    before = decode(candidate["game"])
    if not isinstance(before, GameState):
        raise ControlError(503, "Undo snapshot unavailable")
    _end_vote(control, now_ms)
    control["candidate"] = None
    event["outcome"] = "accepted"
    return before, event


def _end_vote(control: dict, now_ms: int) -> None:
    control["vote"] = None
    timer = control.get("timer")
    if timer is not None and timer.get("deadline_ms") is None and control.get("paused_at") is None:
        timer["deadline_ms"] = now_ms + timer.pop("remaining_ms", 0)


def start_counter(
    control: dict, game: GameState, score: ScoreState, initiator: int, now_ms: int
) -> dict:
    _valid_seat(initiator)
    target = acting_seat(game)
    if target is None or target == initiator:
        raise ControlError(403, "Only an opponent of the decision maker may start a counter")
    if control.get("vote") or control.get("paused_at") is not None:
        raise ControlError(409, "Counter cannot start during a pause or vote")
    if control.get("timer") is not None:
        raise ControlError(409, "A counter is already active")
    price = timer_cost(game, score)
    period = control["policy"]["counter_seconds"] * 1000
    multiplier = control["policy"]["counter_multiplier"]
    timer = {
        "target": target,
        "initiator": initiator,
        "deadline_ms": now_ms + period,
        "cost": price,
        "penalty": multiplier * price,
        "period_ms": period,
        "periods": 0,
        "ruleset_hash": score.ruleset.sha256,
    }
    control["timer"] = timer
    return {k: timer[k] for k in ("target", "initiator", "deadline_ms", "penalty")}


def stop_counter(control: dict) -> None:
    control["timer"] = None


def cancel_counter(control: dict, actor: int, *, admin: bool) -> dict:
    _valid_seat(actor)
    timer = control.get("timer")
    if not timer:
        raise ControlError(409, "No active counter")
    if actor != timer["initiator"] and not admin:
        raise ControlError(403, "Counter initiator or room admin required")
    event = {
        "initiator": timer["initiator"],
        "target": timer["target"],
        "periods": timer["periods"],
    }
    stop_counter(control)
    return event


def tick_controls(
    control: dict, game: GameState | None, score: ScoreState, now_ms: int, deal_id: str | None
) -> tuple[ScoreState, list[dict]]:
    """Reconcile expiration at an atomic server timestamp; no external scheduler.

    A vote timeout is resolved before any counter charges. Disconnected rooms
    remain frozen and cannot incur penalties. `tick_controls` is retry-safe when
    persisted in the same Firestore transaction as its ledger entry.
    """
    events: list[dict] = []
    vote = control.get("vote")
    if (
        vote
        and control.get("paused_at") is None
        and isinstance(vote.get("deadline_ms"), int)
        and now_ms >= vote["deadline_ms"]
    ):
        _end_vote(control, now_ms)
        events.append({"action": "undo_expired", "data": {"kind": vote["kind"]}})
    timer = control.get("timer")
    if not timer or control.get("paused_at") is not None or timer.get("deadline_ms") is None:
        return score, events
    if game is None or acting_seat(game) != timer["target"]:
        stop_counter(control)
        events.append({"action": "counter_stopped", "data": {"reason": "turn_changed"}})
        return score, events
    if now_ms < timer["deadline_ms"]:
        return score, events
    periods = 1 + (now_ms - timer["deadline_ms"]) // timer["period_ms"]
    if periods > MAX_PERIODS_PER_SYNC:
        raise ControlError(503, "Counter requires operator review")
    charge = periods * timer["penalty"]
    target = timer["target"]
    hill = list(score.hill)
    hill[target] += charge
    entry = LedgerEntry(
        len(score.entries) + 1, deal_id or "timer", EntryKind.HILL, target, charge, "counter_180s"
    )
    score = replace(score, hill=tuple(hill), entries=(*score.entries, entry))
    timer["deadline_ms"] += periods * timer["period_ms"]
    timer["periods"] += periods
    events.append(
        {
            "action": "counter_expired",
            "data": {"target": target, "periods": periods, "penalty": charge},
        }
    )
    return score, events


def adjust_score(
    score: ScoreState,
    control: dict,
    field: object,
    seat: object,
    against: object,
    delta: object,
    reason: object,
    actor: int | None,
    now_ms: int,
    deal_id: str,
    version: int,
) -> tuple[ScoreState, dict]:
    """Append-only correction journal, leaving original automatic entries intact."""
    if (
        field not in ("pool", "hill", "vist")
        or type(delta) is not int
        or delta == 0
        or abs(delta) > 1_000
    ):
        raise ControlError(422, "Invalid numeric adjustment")
    if type(seat) is not int or seat not in range(3):
        raise ControlError(422, "Invalid adjustment seat")
    why = _text(reason)
    pools, hills, vists = list(score.pool), list(score.hill), [list(row) for row in score.vists]
    if field == "pool":
        if against is not None:
            raise ControlError(422, "Pool adjustment has no debtor")
        before = pools[seat]
        pools[seat] += delta
        if not 0 <= pools[seat] <= score.target:
            raise ControlError(422, "Pool must stay between zero and target")
        if all(v == score.target for v in pools):
            raise ControlError(409, "Adjustments cannot close all pools")
        after = pools[seat]
    elif field == "hill":
        if against is not None:
            raise ControlError(422, "Hill adjustment has no debtor")
        before = hills[seat]
        hills[seat] += delta
        if hills[seat] < 0:
            raise ControlError(422, "Hill cannot be negative")
        after = hills[seat]
    else:
        if type(against) is not int or against not in range(3) or against == seat:
            raise ControlError(422, "Vist requires another debtor")
        before = vists[seat][against]
        vists[seat][against] += delta
        if vists[seat][against] < 0:
            raise ControlError(422, "Vists cannot be negative")
        after = vists[seat][against]
    next_score = replace(
        score, pool=tuple(pools), hill=tuple(hills), vists=tuple(tuple(row) for row in vists)
    )
    event = {
        "field": field,
        "seat": seat,
        "against": against,
        "delta": delta,
        "before": before,
        "after": after,
        "reason": why,
        "actor_seat": actor,
        "created_at_ms": now_ms,
        "game_version": version,
        "deal_id": deal_id,
    }
    if "score_sheet_adjustments" not in control and control.get("adjustments"):
        control["score_sheet_legacy"] = True
    control["score_sheet_adjustments"] = [
        *control.get("score_sheet_adjustments", []),
        {
            **{key: event[key] for key in ("field", "seat", "against", "delta", "game_version")},
            "ledger_sequence": len(score.entries),
        },
    ]
    control["adjustments"] = [*control.get("adjustments", [])[-19:], event]
    return next_score, event


def public_controls(control: dict, now_ms: int, seat: int | None) -> dict:
    """Strict allowlist: never send undo snapshot or raw user UIDs."""
    timer = control.get("timer")
    vote = control.get("vote")
    return {
        "paused": control.get("paused_at") is not None,
        "pause_reasons": sorted(reasons(control) | ({"undo_vote"} if vote else set())),
        "counter": (
            {
                k: timer[k]
                for k in ("target", "initiator", "deadline_ms", "penalty", "periods", "period_ms")
                if k in timer
            }
            | ({"remaining_ms": timer["remaining_ms"]} if "remaining_ms" in timer else {})
            if timer
            else None
        ),
        "undo": (
            {
                "kind": vote["kind"],
                "requester": vote["requester"],
                "deadline_ms": vote["deadline_ms"],
                **({"remaining_ms": vote["remaining_ms"]} if "remaining_ms" in vote else {}),
                "reason": vote["reason"],
                "votes": vote["votes"].copy(),
                "can_vote": seat is not None
                and control.get("paused_at") is None
                and seat != vote["requester"]
                and str(seat) not in vote["votes"],
            }
            if vote
            else None
        ),
        "can_request_undo": seat is not None
        and not vote
        and control.get("candidate") is not None
        and control["candidate"]["seat"] == seat,
        "adjustments": [a.copy() for a in control.get("adjustments", [])[-20:]],
        "policy": control.get("policy", fresh()["policy"]).copy(),
    }


def reconcile(
    control: dict, game: GameState | None, score: ScoreState, now_ms: int, deal_id: str | None
) -> tuple[ScoreState, list[dict]]:
    """Conservatively freeze a counter when any player's heartbeat becomes stale."""
    if control.get("paused_at") is not None:
        return score, []
    if not (control.get("timer") or control.get("vote")):
        return score, []
    presence = control.get("presence", [None, None, None])
    stale = [seen for seen in presence if seen is None or now_ms - seen > STALE_MS]
    if not stale:
        return tick_controls(control, game, score, now_ms, deal_id)
    known = [seen + STALE_MS for seen in presence if seen is not None and seen + STALE_MS < now_ms]
    frozen_at = min(known) if known else now_ms
    score, events = tick_controls(control, game, score, frozen_at, deal_id)
    transition(control, reasons(control) | {"connection_lost"}, now_ms, freeze_at=frozen_at)
    events.append({"action": "room_paused", "data": {"reason": "heartbeat_stale"}})
    return score, events


def pulse(control: dict, seat: int, now_ms: int) -> dict:
    _valid_seat(seat)
    control["presence"][seat] = now_ms
    if control.get("paused_at") is not None and all(
        seen is not None and now_ms - seen <= STALE_MS for seen in control["presence"]
    ):
        changed = transition(control, reasons(control) - {"connection_lost"}, now_ms)
        return {"resumed": changed and control.get("paused_at") is None}
    return {"resumed": False}


def can_start_counter(control: dict, now_ms: int) -> bool:
    return all(
        seen is not None and now_ms - seen <= STALE_MS for seen in control.get("presence", [])
    )


def configure_policy(control: dict, options: object) -> dict:
    """Numeric-only room policy; immutable once dealing begins."""
    if not isinstance(options, dict) or set(options) != {
        "counter_seconds",
        "counter_multiplier",
        "undo_seconds",
    }:
        raise ControlError(422, "Invalid policy shape")
    for key, lowest, highest in (
        ("counter_seconds", 60, 600),
        ("counter_multiplier", 1, 6),
        ("undo_seconds", 30, 300),
    ):
        value = options[key]
        if type(value) is not int or not lowest <= value <= highest:
            raise ControlError(422, "Invalid numerical room policy")
    control["policy"] = options.copy()
    return {"policy": options.copy()}
