"""Independent durable pause reasons, with conservative recovery of deadlines."""

from __future__ import annotations

from typing import Any


def reasons(control: dict) -> set[str]:
    # Legacy schema stored only a network pause timestamp.
    return set(
        control.get(
            "pause_reasons", ["connection_lost"] if control.get("paused_at") is not None else []
        )
    )


def timer_paused(control: dict, desired: set[str] | None = None) -> bool:
    """A score sheet pauses play, not an already running decision clock."""
    active = reasons(control) if desired is None else desired
    overlay = (control.get("presentation") or {}).get("overlay") or {}
    if overlay.get("kind") == "score_sheet":
        active = active - {"shared_overlay"}
    return bool(active or control.get("vote"))


def transition(control: dict, desired: set[str], at: int, *, freeze_at: int | None = None) -> bool:
    """Reconcile each clock independently, including a replaced shared overlay."""
    previous = reasons(control)
    changed = previous != desired
    if changed:
        control["pause_reasons"] = sorted(desired)
    frozen = at if freeze_at is None else min(at, freeze_at)
    if not previous and desired:
        control["paused_at"] = frozen
    elif previous and not desired:
        control["paused_at"] = None
    for key in ("timer", "vote", "next_deal"):
        clock = control.get(key)
        if not clock:
            continue
        blocked = timer_paused(control, desired) if key == "timer" else bool(desired)
        if key == "next_deal" and control.get("vote"):
            blocked = True
        if blocked and isinstance(clock.get("deadline_ms"), int):
            remaining = max(0, clock["deadline_ms"] - frozen)
            clock["remaining_ms"] = min(5_000, remaining) if key == "next_deal" else remaining
            clock["deadline_ms"] = None
        elif not blocked and clock.get("deadline_ms") is None:
            clock["deadline_ms"] = at + clock.pop(
                "remaining_ms", 5_000 if key == "next_deal" else 0
            )
    return changed


def synchronize(
    control: dict, presence: list[int | None], epoch: str, at: int, *, interrupted: bool = False
) -> list[dict[str, Any]]:
    """Prepare authoritative controls for tick; no charge during unknown downtime.

    On restart or loss freeze at the last durable observation, not at wall-clock
    arrival. This can grant extra time, but cannot manufacture offline penalties.
    Called inside a Firestore transaction, before any tick or game action.
    """
    events: list[dict[str, Any]] = []
    checkpoint = control.get("rt_checkpoint_ms")
    if not isinstance(checkpoint, int) or not 0 <= checkpoint <= at:
        # Rollout from legacy timer: use its start (or old presence) conservatively.
        candidates = [v for v in control.get("presence", []) if isinstance(v, int) and 0 <= v <= at]
        timer = control.get("timer") or {}
        vote = control.get("vote") or {}
        if isinstance(timer.get("deadline_ms"), int):
            candidates.append(max(0, timer["deadline_ms"] - timer.get("period_ms", 180_000)))
        if isinstance(vote.get("deadline_ms"), int):
            candidates.append(
                max(
                    0,
                    vote["deadline_ms"] - control.get("policy", {}).get("undo_seconds", 120) * 1000,
                )
            )
        checkpoint = min(candidates, default=at)
    current = reasons(control)
    if (
        (control.get("rt_epoch") != epoch or interrupted)
        and (control.get("timer") or control.get("vote") or control.get("next_deal"))
    ) or any(v is None for v in presence):
        if transition(control, current | {"connection_lost"}, at, freeze_at=checkpoint):
            events.append({"action": "room_paused", "data": {"reason": "connection_lost"}})
    if all(v is not None for v in presence):
        if transition(control, reasons(control) - {"connection_lost"}, at):
            events.append({"action": "room_resumed", "data": {"reason": "connection_restored"}})
    control["presence"] = presence.copy()
    control["rt_epoch"] = epoch
    control["rt_checkpoint_ms"] = at
    return events


def retire_reveal(control: dict, at: int) -> bool:
    """One-way legacy cleanup; do not remove unrelated pause reasons or postings."""
    changed = "reveal" in control or "revealed_cards" in control
    control.pop("reveal", None)
    control.pop("revealed_cards", None)
    if "accidental_reveal" in reasons(control):
        transition(control, reasons(control) - {"accidental_reveal"}, at)
        changed = True
    return changed
