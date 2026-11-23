"""Pure settlement of a finished PR 2 GameState into an append-only ledger.

No scoring choices are silently invented when the house rules permit two
outcomes: the caller must supply a route in those cases. A game is authoritative
only after its engine has entered FINISHED. The scoring layer never returns cards.
"""

from __future__ import annotations

from enum import Enum

from .auction import BidKind, RuleViolation
from .game import DefenseDecision, EndReason, GameState, Phase
from .ledger import ScoreState, _Posting
from .play import CompletedTrick


class RewardRoute(str, Enum):
    POOL = "pool"
    HILL_FIRST = "hill_first"
    HELP = "help"


def _seat(seat: int) -> None:
    if type(seat) is not int or seat not in range(3):
        raise RuleViolation("Expected one of three player seats")


def _reward_help(post: _Posting, owner: int, amount: int) -> None:
    """Prefer fuller unclosed pools; tie is split, odd point creates 5+5 vists."""
    _seat(owner)
    if type(amount) is not int or amount < 0:
        raise RuleViolation("Positive points must be whole numbers")
    while amount:
        open_others = [s for s in range(3) if s != owner and post.pool[s] < post.rules.pool_target]
        if not open_others:
            for other in range(3):
                if other != owner:
                    post.add_vist(
                        owner,
                        other,
                        post.rules.surplus_vists_per_opponent * amount,
                        "surplus_after_all_pools_closed",
                    )
            return
        if len(open_others) == 2 and post.pool[open_others[0]] == post.pool[open_others[1]]:
            first, second = open_others
            capacity = post.rules.pool_target - post.pool[first]
            pairs = min(amount // 2, capacity)
            if pairs:
                for other in (first, second):
                    post.add_pool(other, pairs, "equal_pool_help")
                    post.add_vist(
                        owner, other, pairs * post.rules.help_vists_per_point, "equal_pool_help"
                    )
                amount -= 2 * pairs
            if amount == 1:
                for other in (first, second):
                    post.add_vist(
                        owner, other, post.rules.surplus_vists_per_opponent, "odd_equal_pool_help"
                    )
                return
            continue
        recipient = max(open_others, key=lambda s: post.pool[s])
        delivered = min(amount, post.rules.pool_target - post.pool[recipient])
        post.add_pool(recipient, delivered, "help_received")
        post.add_vist(owner, recipient, delivered * post.rules.help_vists_per_point, "help_given")
        amount -= delivered


def _regular_reward(post: _Posting, owner: int, amount: int, route: RewardRoute) -> None:
    if route not in (RewardRoute.POOL, RewardRoute.HILL_FIRST):
        raise RuleViolation("Regular rewards require POOL or HILL_FIRST")
    if route == RewardRoute.HILL_FIRST:
        paid = min(amount, post.hill[owner])
        post.pay_hill(owner, paid, "successful_contract_hill_payment")
        amount -= paid
    kept = min(amount, post.rules.pool_target - post.pool[owner])
    post.add_pool(owner, kept, "successful_contract")
    _reward_help(post, owner, amount - kept)


def _passout_bonus(post: _Posting, owner: int, amount: int, route: RewardRoute) -> None:
    """Enforce mandatory pool closure/hill priority, then explicit player choice."""
    _seat(owner)
    gap = post.rules.pool_target - post.pool[owner]
    if gap == 0:
        paid = min(amount, post.hill[owner])
        post.pay_hill(owner, paid, "closed_pool_passout_hill_payment")
        _reward_help(post, owner, amount - paid)
        return
    if amount < gap:
        if route == RewardRoute.POOL:
            post.add_pool(owner, amount, "passout_zero_tricks")
        elif route == RewardRoute.HILL_FIRST and post.hill[owner] > 0:
            paid = min(amount, post.hill[owner])
            post.pay_hill(owner, paid, "passout_hill_payment")
            # If hill was smaller, leftover necessarily enters own unclosed pool.
            post.add_pool(owner, amount - paid, "passout_hill_overflow_to_pool")
        else:
            raise RuleViolation("Choose own pool or available hill for a short passout bonus")
        return
    post.add_pool(owner, gap, "mandatory_passout_pool_closure")
    remainder = amount - gap
    if not remainder:
        return
    if post.hill[owner] and route == RewardRoute.POOL:
        raise RuleViolation("After mandatory pool closure choose HILL_FIRST or HELP")
    if route == RewardRoute.HILL_FIRST:
        paid = min(remainder, post.hill[owner])
        post.pay_hill(owner, paid, "passout_remainder_hill_payment")
        remainder -= paid
    elif route not in (RewardRoute.HELP, RewardRoute.POOL):
        raise RuleViolation("Invalid passout remainder choice")
    _reward_help(post, owner, remainder)


def _defender_hill(
    post: _Posting,
    declarer: int,
    defense: tuple[DefenseDecision | None, ...],
    tricks: tuple[int, int, int],
    level: int,
) -> None:
    rules = post.rules
    visters = [i for i in range(3) if i != declarer and defense[i] == DefenseDecision.VIST]
    if not visters:
        raise RuleViolation("Played regular game requires a visting defender")
    c = rules.cost(level)
    defender_total = 10 - tricks[declarer]
    if len(visters) == 1:
        required = rules.single_vist_required[level - 6]
        short = max(0, required - defender_total)
        post.add_hill(visters[0], short * c, "sole_vister_shortfall")
        post.add_vist(
            visters[0],
            declarer,
            defender_total * c * rules.trick_vist_multiplier,
            "sole_vister_tricks",
        )
        return
    defenders = tuple(i for i in range(3) if i != declarer)
    if level <= 8:
        q = rules.double_personal_required[level - 6]
        for player in defenders:
            other = next(i for i in defenders if i != player)
            uncovered = max(0, q - tricks[player] - max(0, tricks[other] - q))
            post.add_hill(player, uncovered * c, "joint_vister_shortfall")
    elif defender_total == 0:
        for player in defenders:
            post.add_hill(player, c, "joint_vister_zero_tricks")
    for player in defenders:
        post.add_vist(
            player,
            declarer,
            tricks[player] * c * rules.trick_vist_multiplier,
            "individual_vister_tricks",
        )


def _check_finished(game: GameState) -> None:
    if not isinstance(game, GameState) or game.phase != Phase.FINISHED:
        raise RuleViolation("Only a completed engine deal may be settled")
    if game.end_reason not in (
        EndReason.PLAYED,
        EndReason.HALF_VIST,
        EndReason.ALL_PASSED,
        EndReason.WITHOUT_THREE,
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
    elif game.completed_tricks or game.trick or any(game.tricks_won):
        raise RuleViolation("An unplayed deal cannot claim taken tricks")
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

    Passout deals with two zero-trick winners require explicit reward order:
    their bonuses may both cause help or close a pool. This ordering is a room
    decision, not an implicit implementation detail.
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

    if game.is_passout:
        if game.end_reason != EndReason.PLAYED:
            raise RuleViolation("Passout games must be played to completion")
        for player, count in enumerate(game.tricks_won):
            post.add_hill(
                player, count * rules.passout_cost(ledger.passout_level), "passout_taken_tricks"
            )
        zero_winners = tuple(i for i, count in enumerate(game.tricks_won) if count == 0)
        if len(zero_winners) > 1 and passout_reward_order is None:
            raise RuleViolation("Explicit reward order required for simultaneous passout bonuses")
        order = zero_winners if passout_reward_order is None else passout_reward_order
        if (
            type(order) is not tuple
            or len(order) != len(zero_winners)
            or any(type(i) is not int or i not in range(3) for i in order)
            or set(order) != set(zero_winners)
        ):
            raise RuleViolation("Reward order must include each zero-trick seat exactly once")
        for player in order:
            _passout_bonus(
                post, player, rules.passout_cost(ledger.passout_level), passout_routes[player]
            )
        next_passout = 6 if ledger.passout_level == 8 else ledger.passout_level + 1
    else:
        declarer = game.declarer
        contract = game.contract
        assert declarer is not None and contract is not None
        _seat(declarer)
        if contract.kind in (BidKind.MISERE, BidKind.MISERE_NO_WIDOW):
            if game.end_reason != EndReason.PLAYED:
                raise RuleViolation("Misere cannot end with a concession or half-vist")
            tricks = game.tricks_won[declarer]
            if tricks:
                post.add_hill(declarer, tricks * rules.misere_cost, "misere_taken_tricks")
            else:
                _regular_reward(post, declarer, rules.misere_cost, RewardRoute.POOL)
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
                _regular_reward(post, declarer, cost, regular_route)
            elif game.end_reason == EndReason.PLAYED:
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
                    _regular_reward(post, declarer, cost, regular_route)
                    next_passout = 6
                _defender_hill(post, declarer, game.defense, game.tricks_won, level)
    return post.finish(ledger, next_passout)
