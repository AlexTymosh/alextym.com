"""Presentation metadata only: the authoritative deck always contains 32 cards."""

GAG_FAKE_MS = 8000
GAG_TOTAL_MS = 11900


def record_discard(control: dict, game_id: str, seat: int, at_ms: int, hide: bool) -> None:
    if hide:
        control["hidden_discard"] = {"game_id": game_id, "seat": seat, "at_ms": at_ms}
    else:
        control.pop("hidden_discard", None)


def begin(control: dict, previous_game_id: str | None, game_id: str, at_ms: int) -> bool:
    """Consume the joke exactly once, in the same transaction as the next deal."""
    hidden = control.pop("hidden_discard", None)
    control.pop("redeal_gag", None)
    if hidden and hidden.get("game_id") == previous_game_id:
        control["redeal_gag"] = {"game_id": game_id, "seat": hidden["seat"], "at_ms": at_ms}
        return True
    return False


def active(control: dict, game_id: str | None, now_ms: int) -> bool:
    gag = control.get("redeal_gag") or {}
    return bool(game_id and gag.get("game_id") == game_id and now_ms < gag["at_ms"] + GAG_TOTAL_MS)


def project(control: dict, game_id: str | None, *, auction: bool) -> dict:
    """Only seat and server timestamp; never the identities of the hidden cards."""
    result = {}
    hidden = control.get("hidden_discard") or {}
    if game_id and hidden.get("game_id") == game_id:
        result["hidden_discard"] = {key: hidden[key] for key in ("seat", "at_ms")}
    gag = control.get("redeal_gag") or {}
    if auction and game_id and gag.get("game_id") == game_id:
        result["redeal_gag"] = {key: gag[key] for key in ("seat", "at_ms")}
    return result
