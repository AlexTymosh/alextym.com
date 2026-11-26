"""Small public UI projections derived from authoritative game state."""

import json

from preferans.domain.reward_routing import blocked_players, passout_options, priority_targets

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
        [game.claim.seat, game.claim.at_tricks, game.claim.rejected_by, game.claim.accepted]
        if getattr(game, "claim", None) is not None
        else None,
    ]
    key = json.dumps(key, separators=(",", ":"))
    if room.get("activity_key") != key:
        room["activity_key"] = key
        room["activity_started_at_ms"] = now


def settlement_options(score, game, selected=None):
    result = {"regular_choice": False, "passout_defaults": ["pool"] * 3}
    if game.is_passout:
        result.update(passout_options(score, game, selected))
    elif game.contract and game.declarer is not None and not game.is_misere:
        seat = game.declarer
        level = game.contract.level
        reason = game.end_reason.value if game.end_reason else ""
        won = reason in ("all_passed", "half_vist") or (
            level is not None
            and reason in ("played", "all_mine_accepted")
            and game.tricks_won[seat] >= level
        )
        _, denied = priority_targets(
            score.pool, score.target, seat, blocked_players(game, score.ruleset.rules)
        )
        result["regular_choice"] = bool(
            won and score.pool[seat] >= score.target and score.hill[seat] > 0 and not denied
        )
    return result
