"""Priority and penalty eligibility shared by settlement and UI projection.

Only penalties for the outcome of this deal count, never existing hill,
manual adjustments or counter penalties.
"""

from .auction import RuleViolation
from .game import DefenseDecision, EndReason


def defender_shortfalls(rules, declarer, defense, tricks, level):
    visters = [i for i in range(3) if i != declarer and defense[i] == DefenseDecision.VIST]
    if not visters:
        raise RuleViolation("Played regular game requires a visting defender")
    total = 10 - tricks[declarer]
    if len(visters) == 1:
        return {visters[0]: max(0, rules.single_vist_required[level - 6] - total)}
    if level > 8:
        return {i: int(total == 0) for i in visters}
    required = rules.double_personal_required[level - 6]
    return {
        i: max(0, required - tricks[i] - max(0, tricks[j] - required))
        for i, j in ((visters[0], visters[1]), (visters[1], visters[0]))
    }


def blocked_players(game, rules):
    if game.is_passout:
        return frozenset(i for i, n in enumerate(game.tricks_won) if n)
    if game.declarer is None or game.contract is None:
        return frozenset()
    if game.is_misere:
        return frozenset({game.declarer}) if game.tricks_won[game.declarer] else frozenset()
    if game.end_reason == EndReason.WITHOUT_THREE:
        return frozenset({game.declarer})
    if game.end_reason not in (EndReason.PLAYED, EndReason.ALL_MINE_ACCEPTED):
        return frozenset()
    level = game.contract.level
    blocked = {
        i
        for i, n in defender_shortfalls(
            rules, game.declarer, game.defense, game.tricks_won, level
        ).items()
        if n
    }
    if game.tricks_won[game.declarer] < level:
        blocked.add(game.declarer)
    return frozenset(blocked)


def priority_targets(pool, target, owner, blocked):
    """Return eligible highest-priority recipients and whether help is blocked.

    A penalised sole higher pool blocks help, rather than redirecting it to a
    lower pool. Equal highest pools allow the non-penalised player to receive all.
    """
    opened = [i for i in range(3) if i != owner and pool[i] < target]
    if not opened:
        return [], False
    maximum = max(pool[i] for i in opened)
    eligible = [i for i in opened if pool[i] == maximum and i not in blocked]
    return eligible, not eligible


def passout_options(score, game, selected=None):
    """Stage own bonus choices before exposing exact possible help recipients."""
    selected = selected or {}
    amount = score.ruleset.rules.passout_cost(score.passout_level)
    blocked = blocked_players(game, score.ruleset.rules)
    pool = list(score.pool)
    defaults = ["pool"] * 3
    choices = [[], [], []]
    targets = [[], [], []]
    pending = []

    def choose(i, allowed):
        choices[i] = allowed
        if selected.get(str(i)) in allowed:
            defaults[i] = selected[str(i)]
        else:
            pending.append(i)

    for i in range(3):
        if i in blocked:
            continue
        gap = score.target - score.pool[i]
        if gap <= amount:
            pool[i] = score.target
            if gap < amount and score.hill[i] > 0:
                defaults[i] = "hill_first"
        else:
            pool[i] += amount
    # Stage mandatory own-pool credits before computing help priorities.
    if not pending:
        for i in range(3):
            if i in blocked:
                continue
            gap = score.target - score.pool[i]
            targets[i], denied = priority_targets(pool, score.target, i, blocked)
            if gap < amount and score.hill[i] > 0 and not denied:
                choose(i, ["hill_first", "help"])
    return {
        "passout_defaults": defaults,
        "passout_choices": choices,
        "passout_targets": targets,
        "passout_pending": pending,
    }
