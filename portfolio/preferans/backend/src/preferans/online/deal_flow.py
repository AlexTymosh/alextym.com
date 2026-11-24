"""Durable five-second deadline for the next deal, never a client-side decision."""

NEXT_DEAL_MS = 5_000


def schedule(control: dict, game_id: str, at: int) -> None:
    control["next_deal"] = {"after_game_id": game_id, "deadline_ms": at + NEXT_DEAL_MS}
    if control.get("paused_at") is not None or control.get("vote"):
        control["next_deal"].update(deadline_ms=None, remaining_ms=NEXT_DEAL_MS)


def due(control: dict, game_id: str | None, at: int) -> bool:
    clock = control.get("next_deal") or {}
    deadline = clock.get("deadline_ms")
    return (
        game_id is not None
        and clock.get("after_game_id") == game_id
        and type(deadline) is int
        and at >= deadline
        and control.get("paused_at") is None
        and not control.get("vote")
        and len(control.get("presence", [])) == 3
        and all(type(seen) is int for seen in control["presence"])
    )


def projection(control: dict, game_id: str | None) -> dict | None:
    clock = control.get("next_deal") or {}
    if not game_id or clock.get("after_game_id") != game_id:
        return None
    return {
        "after_game_id": game_id,
        "deadline_ms": clock.get("deadline_ms"),
        "remaining_ms": clock.get("remaining_ms"),
    }
