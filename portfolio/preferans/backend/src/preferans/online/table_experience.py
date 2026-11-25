"""Small public UI projections derived from authoritative game state."""

import json

THEMES = ("felt", "blue", "wood", "glass")


def mark_activity(room, game, now):
    if game is None or room["status"] != "playing":
        room.pop("activity_key", None)
        room.pop("activity_started_at_ms", None)
        return
    key = [
        room["game_id"],
        game.phase.value,
        game.turn,
        game.declarer,
        len(game.auction.history),
        len(game.completed_tricks),
        len(game.trick),
        [d.value if d else None for d in game.defense],
        game.mode.value if game.mode else None,
    ]
    key = json.dumps(key, separators=(",", ":"))
    if room.get("activity_key") != key:
        room["activity_key"] = key
        room["activity_started_at_ms"] = now


def settlement_options(score, game):
    """Hide meaningless choices; do not modify the accounting engine.

    Own open pools receive regular rewards first. Passout routes obey the
    engine's mandatory closure and remainder constraints.
    """
    choices = False
    defaults = ["pool", "pool", "pool"]
    if game.is_passout:
        amount = score.ruleset.rules.passout_cost(score.passout_level)
        for seat, tricks in enumerate(game.tricks_won):
            gap = score.target - score.pool[seat]
            if tricks == 0 and 0 < gap < amount and score.hill[seat] > 0:
                defaults[seat] = "hill_first"
    elif game.contract and game.declarer is not None:
        seat = game.declarer
        level = game.contract.level
        won = game.end_reason.value in ("all_passed", "half_vist") if game.end_reason else False
        if level is not None and game.end_reason and game.end_reason.value == "played":
            won = game.tricks_won[seat] >= level
        choices = bool(
            level is not None and won and score.pool[seat] >= score.target and score.hill[seat] > 0
        )
    return {"regular_choice": choices, "passout_defaults": defaults}
