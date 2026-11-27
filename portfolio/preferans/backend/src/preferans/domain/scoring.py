"""Pure settlement of a finished PR 2 GameState into an append-only ledger.

No scoring choices are silently invented when the house rules permit two
outcomes: the caller must supply a route in those cases. A game is authoritative
only after its engine has entered FINISHED. The scoring layer never returns cards.
"""

from __future__ import annotations

from enum import Enum
from copy import deepcopy

from .auction import BidKind, RuleViolation
from .game import DefenseDecision, EndReason, GameState, Phase
from .ledger import EntryKind, ScoreState, _Posting
from .play import CompletedTrick
from .claims import claim_awards, claim_voters
from .reward_routing import blocked_players, defender_shortfalls, priority_targets


class RewardRoute(str, Enum):
    POOL = "pool"
    HILL_FIRST = "hill_first"
    HELP = "help"


def _seat(seat: int) -> None:
    if type(seat) is not int or seat not in range(3):
        raise RuleViolation("Expected one of three player seats")


def _surplus(post: _Posting, owner: int, amount: int, reason: str) -> None:
    for other in range(3):
        if other != owner:
            post.add_vist(owner, other, post.rules.surplus_vists_per_opponent * amount, reason)


def _reward_help(post: _Posting, owner: int, amount: int, blocked: frozenset[int]) -> None:
    """Use the priority group; penalised recipients cannot receive points."""
    _seat(owner)
    if type(amount) is not int or amount < 0:
        raise RuleViolation("Positive points must be whole numbers")
    while amount:
        targets, denied = priority_targets(post.pool, post.rules.pool_target, owner, blocked)
        if denied:
            paid = min(amount, post.hill[owner])
            post.pay_hill(owner, paid, "blocked_help_hill_payment")
            _surplus(post, owner, amount - paid, "blocked_help_surplus")
            return
        if not targets:
            _surplus(post, owner, amount, "surplus_after_all_pools_closed")
            return
        if len(targets) == 2:
            pairs = min(amount // 2, post.rules.pool_target - post.pool[targets[0]])
            for other in targets:
                post.add_pool(other, pairs, "equal_pool_help")
                post.add_vist(
                    owner, other, pairs * post.rules.help_vists_per_point, "equal_pool_help"
                )
            amount -= 2 * pairs
            if amount == 1:
                _surplus(post, owner, amount, "odd_equal_pool_help")
                return
            continue
        recipient = targets[0]
        delivered = min(amount, post.rules.pool_target - post.pool[recipient])
        post.add_pool(recipient, delivered, "help_received")
        post.add_vist(owner, recipient, delivered * post.rules.help_vists_per_point, "help_given")
        amount -= delivered


def _regular_reward(
    post: _Posting, owner: int, amount: int, route: RewardRoute, blocked: frozenset[int]
) -> None:
    if route not in (RewardRoute.POOL, RewardRoute.HILL_FIRST):
        raise RuleViolation("Regular rewards require POOL or HILL_FIRST")
    if route == RewardRoute.HILL_FIRST:
        if post.pool[owner] != post.rules.pool_target:
            raise RuleViolation("Close own pool before paying hill")
        paid = min(amount, post.hill[owner])
        post.pay_hill(owner, paid, "successful_contract_hill_payment")
        amount -= paid
    kept = min(amount, post.rules.pool_target - post.pool[owner])
    post.add_pool(owner, kept, "successful_contract")
    _reward_help(post, owner, amount - kept, blocked)


def _stage_passout_bonus(post: _Posting, owner: int, amount: int, route: RewardRoute) -> int:
    """Apply the own-pool/hill portion before any help is distributed."""
    _seat(owner)
    gap = post.rules.pool_target - post.pool[owner]
    if gap == 0:
        if route != RewardRoute.HELP:
            paid = min(amount, post.hill[owner])
            post.pay_hill(owner, paid, "closed_pool_passout_hill_payment")
            return amount - paid
        return amount
    if amount <= gap:
        if route != RewardRoute.POOL:
            raise RuleViolation("Passout reward must fill the open pool first")
        post.add_pool(
            owner,
            amount,
            "passout_zero_tricks" if amount < gap else "mandatory_passout_pool_closure",
        )
        return 0
    post.add_pool(owner, gap, "mandatory_passout_pool_closure")
    remainder = amount - gap
    if not remainder:
        return 0
    if post.hill[owner] and route == RewardRoute.POOL:
        raise RuleViolation("After mandatory pool closure choose HILL_FIRST or HELP")
    if route == RewardRoute.HILL_FIRST:
        paid = min(remainder, post.hill[owner])
        post.pay_hill(owner, paid, "passout_remainder_hill_payment")
        remainder -= paid
    return remainder


def _passout_bonus(post, owner, amount, route, blocked):
    remainder = _stage_passout_bonus(post, owner, amount, route)
    _reward_help(post, owner, remainder, blocked)


def _simultaneous_passout_bonuses(post, owners, amount, routes, blocked):
    """Determine all own credits first and plan help from a single snapshot."""
    remainder = {
        owner: _stage_passout_bonus(post, owner, amount, routes[owner]) for owner in owners
    }
    desires = {}
    direct = {}
    for owner in owners:
        trial = deepcopy(post)
        base = len(trial.entries)
        _reward_help(trial, owner, remainder[owner], blocked)
        desires[owner] = {}
        direct[owner] = []
        for entry in trial.entries[base:]:
            if entry.kind == EntryKind.POOL:
                desires[owner][entry.actor] = desires[owner].get(entry.actor, 0) + entry.amount
            elif entry.kind == EntryKind.HILL_PAYMENT or (
                entry.kind == EntryKind.VIST
                and entry.reason not in ("equal_pool_help", "help_given")
            ):
                direct[owner].append(entry)
    for target in range(3):
        requests = {owner: desires[owner].get(target, 0) for owner in owners}
        total = sum(requests.values())
        if not total:
            continue
        capacity = post.rules.pool_target - post.pool[target]
        for owner, intended in requests.items():
            granted = intended if total <= capacity else intended * capacity // total
            if granted:
                post.add_pool(target, granted, "simultaneous_help_received")
                post.add_vist(
                    owner,
                    target,
                    granted * post.rules.help_vists_per_point,
                    "simultaneous_help_given",
                )
            if intended > granted:
                _surplus(post, owner, intended - granted, "simultaneous_help_unallocated")
    for owner in owners:
        for entry in direct[owner]:
            if entry.kind == EntryKind.HILL_PAYMENT:
                post.pay_hill(owner, entry.amount, entry.reason)
            else:
                post.add_vist(owner, entry.against, entry.amount, entry.reason)


def _defender_hill(
    post: _Posting,
    declarer: int,
    defense: tuple[DefenseDecision | None, ...],
    tricks: tuple[int, int, int],
    level: int,
) -> None:
    rules = post.rules
    visters = [i for i in range(3) if i != declarer and defense[i] == DefenseDecision.VIST]
    shortfalls = defender_shortfalls(rules, declarer, defense, tricks, level)
    c = rules.cost(level)
    for i, short in shortfalls.items():
        reason = (
            "sole_vister_shortfall"
            if len(visters) == 1
            else ("joint_vister_shortfall" if level <= 8 else "joint_vister_zero_tricks")
        )
        post.add_hill(i, short * c, reason)
    for i in visters:
        count = 10 - tricks[declarer] if len(visters) == 1 else tricks[i]
        post.add_vist(
            i,
            declarer,
            count * c * rules.trick_vist_multiplier,
            "sole_vister_tricks" if len(visters) == 1 else "individual_vister_tricks",
        )


def _check_finished(game: GameState) -> None:
    if not isinstance(game, GameState) or game.phase != Phase.FINISHED:
        raise RuleViolation("Only a completed engine deal may be settled")
    if game.end_reason not in (
        EndReason.PLAYED,
        EndReason.HALF_VIST,
        EndReason.ALL_PASSED,
        EndReason.WITHOUT_THREE,
        EndReason.MISERE_ACCEPTED,
        EndReason.ALL_MINE_ACCEPTED,
    ):
        raise RuleViolation("Unsupported engine end reason")
    if game.end_reason == EndReason.PLAYED:
        if (
            len(game.completed_tricks) != 10
            or game.trick
            or sum(game.tricks_won) != 10
            or any(type(t) is not int or t not in range(11) for t in game.tricks_won)
        ):
            raise RuleViolation("A played deal must have ten completed tricks")
        if any(
            not isinstance(t, CompletedTrick) or t.number != i
            for i, t in enumerate(game.completed_tricks, 1)
        ):
            raise RuleViolation("Completed tricks must have valid sequential records")
        if any(
            sum(t.winner == player for t in game.completed_tricks) != game.tricks_won[player]
            for player in range(3)
        ):
            raise RuleViolation("Winner counts disagree with completed trick records")
    elif game.end_reason == EndReason.ALL_MINE_ACCEPTED:
        claim = game.claim
        count = len(game.completed_tricks)
        if (
            claim is None
            or not claim.accepted
            or claim.rejected_by is not None
            or type(claim.seat) is not int
            or claim.seat not in range(3)
            or claim.at_tricks != count
            or not 0 <= count < 10
            or not claim.approved
            or claim.approved != claim_voters(game, claim.seat)
            or game.trick
            or any(game.hands)
            or len(claim.partial) > 2
            or any(
                not isinstance(t, CompletedTrick) or t.number != i
                for i, t in enumerate(game.completed_tricks, 1)
            )
            or tuple(
                sum(t.winner == i for t in game.completed_tricks)
                + claim_awards(game, claim.seat, claim.defender_target)[i]
                for i in range(3)
            )
            != game.tricks_won
        ):
            raise RuleViolation("Invalid consensual remaining-tricks result")
    elif game.end_reason == EndReason.MISERE_ACCEPTED:
        if (
            game.is_passout
            or not game.is_misere
            or game.winning_bid != game.contract
            or game.declarer not in range(3)
            or game.misere_votes != frozenset(range(3)) - {game.declarer}
            or len(game.discarded) != (2 if game.contract.uses_widow else 0)
            or game.trick
            or game.tricks_won[game.declarer] != 0
            or not 0 <= len(game.completed_tricks) < 10
            or any(
                not isinstance(t, CompletedTrick) or t.number != i or t.winner not in range(3)
                for i, t in enumerate(game.completed_tricks, 1)
            )
            or tuple(sum(t.winner == i for t in game.completed_tricks) for i in range(3))
            != game.tricks_won
        ):
            raise RuleViolation(
                "Misere acceptance requires both defenders and a successful actual history"
            )
    elif game.completed_tricks or game.trick or any(game.tricks_won):
        raise RuleViolation("An unplayed deal cannot claim taken tricks")
    if game.end_reason == EndReason.WITHOUT_THREE and (
        game.is_passout
        or game.winning_bid is None
        or game.contract != game.winning_bid
        or game.winning_bid.kind not in (BidKind.REGULAR, BidKind.TEN_NO_WIDOW)
        or any(game.defense)
    ):
        raise RuleViolation("Without-three requires the winning bid and no defense decisions")
    if not game.is_passout and (game.declarer is None or game.contract is None):
        raise RuleViolation("A declarer and final contract are required")


def settle_game(
    ledger: ScoreState,
    game: GameState,
    deal_id: str,
    *,
    regular_route: RewardRoute = RewardRoute.POOL,
    passout_routes: tuple[RewardRoute, RewardRoute, RewardRoute] = (
        RewardRoute.POOL,
        RewardRoute.POOL,
        RewardRoute.POOL,
    ),
    passout_reward_order: tuple[int, ...] | None = None,
    expected_version: int | None = None,
) -> ScoreState:
    """Apply one deal atomically, without modifying either input object.

    Multiple zero-trick passout bonuses are staged simultaneously, without
    allocating first-mover priority to either winner.
    """
    if not isinstance(ledger, ScoreState):
        raise TypeError("Expected a ScoreState")
    if not isinstance(deal_id, str) or not deal_id.strip() or len(deal_id) > 128:
        raise RuleViolation("A short nonempty deal ID is required")
    if deal_id in ledger.deal_ids:
        raise RuleViolation("A deal can only be settled once")
    if ledger.closed:
        raise RuleViolation("All pools were already closed; no new deal is allowed")
    if expected_version is not None and (
        type(expected_version) is not int or expected_version != ledger.version
    ):
        raise RuleViolation("Stale scoring version")
    _check_finished(game)
    if game.passout_level != ledger.passout_level:
        raise RuleViolation("Game passout level differs from the current ledger")
    if not isinstance(regular_route, RewardRoute):
        raise RuleViolation("Invalid regular reward route")
    if len(passout_routes) != 3 or any(not isinstance(v, RewardRoute) for v in passout_routes):
        raise RuleViolation("Passout routes must contain three choices")
    post = _Posting(ledger, deal_id)
    rules = ledger.ruleset.rules
    next_passout = ledger.passout_level
    blocked = blocked_players(game, rules)

    if game.is_passout:
        if game.end_reason not in (EndReason.PLAYED, EndReason.ALL_MINE_ACCEPTED):
            raise RuleViolation("Passout games must be played to completion")
        for player, count in enumerate(game.tricks_won):
            post.add_hill(
                player, count * rules.passout_cost(ledger.passout_level), "passout_taken_tricks"
            )
        zero_winners = tuple(i for i, count in enumerate(game.tricks_won) if count == 0)
        if passout_reward_order is not None:
            raise RuleViolation("Sequential passout reward order is forbidden by house rules")
        if len(zero_winners) > 1:
            _simultaneous_passout_bonuses(
                post,
                zero_winners,
                rules.passout_cost(ledger.passout_level),
                passout_routes,
                blocked,
            )
        else:
            for player in zero_winners:
                _passout_bonus(
                    post,
                    player,
                    rules.passout_cost(ledger.passout_level),
                    passout_routes[player],
                    blocked,
                )
        next_passout = 6 if ledger.passout_level == 8 else ledger.passout_level + 1
    else:
        declarer = game.declarer
        contract = game.contract
        assert declarer is not None and contract is not None
        _seat(declarer)
        if contract.kind in (BidKind.MISERE, BidKind.MISERE_NO_WIDOW):
            if game.end_reason not in (
                EndReason.PLAYED,
                EndReason.MISERE_ACCEPTED,
                EndReason.ALL_MINE_ACCEPTED,
            ):
                raise RuleViolation("Misere cannot end with a concession or half-vist")
            tricks = game.tricks_won[declarer]
            if tricks:
                post.add_hill(declarer, tricks * rules.misere_cost, "misere_taken_tricks")
            else:
                _regular_reward(post, declarer, rules.misere_cost, RewardRoute.POOL, blocked)
        else:
            level = contract.level
            assert level is not None
            cost = rules.cost(level)
            if game.end_reason == EndReason.WITHOUT_THREE:
                post.add_hill(declarer, cost * 3, "conceded_without_three")
            elif game.end_reason in (EndReason.HALF_VIST, EndReason.ALL_PASSED):
                if level <= 7:
                    expected_receiver = (declarer + 2) % 3
                    if game.half_vist_receiver != expected_receiver:
                        raise RuleViolation("Automatic half-vist belongs to the far defender")
                    post.add_vist(
                        expected_receiver, declarer, rules.half_vist_award, "automatic_half_vist"
                    )
                elif game.half_vist_receiver is not None or game.end_reason == EndReason.HALF_VIST:
                    raise RuleViolation("Half-vist is available only on 6/7")
                _regular_reward(post, declarer, cost, regular_route, blocked)
                next_passout = 6  # Confirmed: automatic contract wins reset passouts.
            elif game.end_reason in (EndReason.PLAYED, EndReason.ALL_MINE_ACCEPTED):
                _defender_hill(post, declarer, game.defense, game.tricks_won, level)
                taken = game.tricks_won[declarer]
                missing = max(0, level - taken)
                if missing:
                    post.add_hill(declarer, missing * cost, "contract_shortfall")
                    for defender in range(3):
                        if defender != declarer:
                            post.add_vist(
                                defender,
                                declarer,
                                missing * cost * rules.consolation_multiplier,
                                "consolation",
                            )
                else:
                    _regular_reward(post, declarer, cost, regular_route, blocked)
                    next_passout = 6
    return post.finish(ledger, next_passout)
