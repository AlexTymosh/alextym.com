"""Golden numeric checks anchored to house rules and technical spec section 25."""

from dataclasses import replace

import pytest

from preferans.domain import (
    AuctionOutcome,
    Bid,
    DefenseDecision,
    CompletedTrick,
    PlayedCard,
    EndReason,
    FULL_DECK,
    Phase,
    RewardRoute,
    RuleViolation,
    ScoreState,
    Suit,
    concede_without_three,
    deal,
    start_game,
    settle_game,
)


def ledger(pool=(0, 0, 0), hill=(0, 0, 0), *, passout=6):
    return replace(
        ScoreState.new(),
        pool=pool,
        hill=hill,
        passout_level=passout,
        closed=all(v == 20 for v in pool),
    )


def played(
    level=6,
    tricks=(5, 3, 2),
    defense=(None, DefenseDecision.VIST, DefenseDecision.VIST),
    contract=None,
    reason=EndReason.PLAYED,
):
    base = start_game(deal(FULL_DECK, 2))
    return replace(
        base,
        phase=Phase.FINISHED,
        declarer=0,
        contract=contract if contract is not None else Bid.regular(level, Suit.HEARTS),
        tricks_won=tricks if reason == EndReason.PLAYED else (0, 0, 0),
        # Unit synthetic engine output: the existing engine's full-play tests
        # independently prove that actual CompletedTrick objects have 10 entries.
        completed_tricks=tuple(
            CompletedTrick(
                number,
                (
                    PlayedCard(0, 0, FULL_DECK[0]),
                    PlayedCard(1, 1, FULL_DECK[8]),
                    PlayedCard(2, 2, FULL_DECK[16]),
                ),
                owner,
                Suit.SPADES,
            )
            for number, owner in enumerate(
                (0,) * tricks[0] + (1,) * tricks[1] + (2,) * tricks[2], 1
            )
        )
        if reason == EndReason.PLAYED
        else (),
        end_reason=reason,
        defense=defense,
        turn=None,
    )


def passouts(tricks, *, level=6):
    game = played(tricks=tricks)
    return replace(
        game,
        auction=replace(game.auction, outcome=AuctionOutcome.PASSOUT),
        contract=None,
        declarer=None,
        passout_level=level,
    )


def settle(game, *, points=None, deal_id="d1", **kwargs):
    state = ledger() if points is None else points
    return settle_game(state, game, deal_id, **kwargs)


def test_six_3_and_2_defender_tricks_golden():
    state = settle(played())
    assert state.hill == (2, 0, 0)
    assert state.vists[1][0] == 16
    assert state.vists[2][0] == 12
    assert state.pool == (0, 0, 0)


@pytest.mark.parametrize(
    ("first", "second", "hill_first", "hill_second"),
    [
        (4, 0, 0, 0),
        (3, 0, 0, 2),
        (2, 1, 0, 2),
        (2, 0, 0, 4),
        (1, 1, 2, 2),
        (1, 0, 2, 4),
        (0, 0, 4, 4),
    ],
)
def test_two_visters_level_six_confirmed_table(first, second, hill_first, hill_second):
    state = settle(played(tricks=(10 - first - second, first, second)))
    assert state.hill[1:] == (hill_first, hill_second)


@pytest.mark.parametrize(
    ("level", "first", "second", "hill_first", "hill_second"),
    [
        (7, 2, 0, 0, 0),
        (7, 1, 0, 0, 4),
        (7, 0, 0, 4, 4),
        (8, 2, 0, 0, 0),
        (8, 1, 0, 0, 6),
        (8, 0, 0, 6, 6),
        (9, 0, 0, 8, 8),
        (10, 0, 0, 10, 10),
    ],
)
def test_other_two_vister_golden_rows(level, first, second, hill_first, hill_second):
    state = settle(played(level, (10 - first - second, first, second)))
    assert state.hill[1:] == (hill_first, hill_second)


def test_single_vister_owns_all_defender_tricks_and_consolation():
    game = played(7, (6, 2, 2), (None, DefenseDecision.VIST, DefenseDecision.PASS))
    state = settle(game)
    assert state.hill == (4, 0, 0)
    assert state.vists[1][0] == 40  # 4 * 8 + 8 consolidation
    assert state.vists[2][0] == 8


def test_single_vister_six_shortfall_one_trick():
    game = played(6, (9, 1, 0), (None, DefenseDecision.VIST, DefenseDecision.PASS))
    state = settle(game)
    assert state.hill[1] == 6


def test_level_eight_one_and_two_visters_different_requirements():
    solo = played(8, (9, 1, 0), (None, DefenseDecision.VIST, DefenseDecision.PASS))
    two = played(8, (9, 1, 0))
    assert settle(solo).hill[1:] == (0, 0)
    assert settle(two).hill[1:] == (0, 6)


def test_extra_tricks_do_not_increase_regular_reward():
    assert settle(played(6, (8, 1, 1))).pool[0] == 2


@pytest.mark.parametrize("contract", [Bid.misere(), Bid.misere_no_widow()])
def test_misere_success_and_failure(contract):
    assert (
        settle(played(contract=contract, tricks=(0, 5, 5), defense=(None, None, None))).pool[0]
        == 10
    )
    fail = settle(played(contract=contract, tricks=(2, 4, 4), defense=(None, None, None)))
    assert fail.hill == (20, 0, 0)
    assert fail.vists[1][0] == 0


def test_ten_no_widow_has_the_ten_cost():
    game = played(10, (10, 0, 0), contract=Bid.ten_no_widow(Suit.SPADES))
    assert settle(game).pool[0] == 10


@pytest.mark.parametrize("level", [6, 7])
def test_two_passing_defenders_auto_half_vist(level):
    game = replace(played(level, reason=EndReason.ALL_PASSED), half_vist_receiver=2)
    state = settle(game)
    assert state.pool[0] == 2 * (level - 5)
    assert state.vists[2][0] == 8
    assert state.hill == (0, 0, 0)


def test_half_vist_reason_rewards_second_defender_only():
    game = replace(played(7, reason=EndReason.HALF_VIST), half_vist_receiver=2)
    assert settle(game).vists[2][0] == 8


def test_two_passers_at_level_eight_get_no_auto_vists():
    game = replace(played(8, reason=EndReason.ALL_PASSED), half_vist_receiver=None)
    assert settle(game).vists == ((0, 0, 0),) * 3


def test_without_three_declaration_before_first_card():
    game = replace(
        start_game(deal(FULL_DECK, 2)),
        phase=Phase.DEFENSE_FIRST,
        declarer=0,
        contract=Bid.regular(7, Suit.HEARTS),
        turn=1,
    )
    conceded = concede_without_three(game, 0)
    assert conceded.end_reason == EndReason.WITHOUT_THREE
    state = settle(conceded)
    assert state.hill == (12, 0, 0)
    assert state.vists == ((0, 0, 0),) * 3


def test_without_three_allowed_for_ten_no_widow():
    game = replace(
        start_game(deal(FULL_DECK, 2)),
        phase=Phase.PLAY,
        declarer=0,
        contract=Bid.ten_no_widow(Suit.HEARTS),
    )
    assert settle(concede_without_three(game, 0)).hill[0] == 30


def test_without_three_misere_forbidden():
    game = replace(
        start_game(deal(FULL_DECK, 2)), phase=Phase.PLAY, declarer=0, contract=Bid.misere()
    )
    with pytest.raises(RuleViolation):
        concede_without_three(game, 0)


def test_without_three_after_first_play_forbidden():
    game = replace(
        start_game(deal(FULL_DECK, 2)),
        phase=Phase.PLAY,
        declarer=0,
        contract=Bid.regular(7, Suit.HEARTS),
        trick=(1,),
    )
    with pytest.raises(RuleViolation):
        concede_without_three(game, 0)


def test_regular_hill_first_is_all_or_nothing_before_pool():
    start = ledger(hill=(3, 0, 0))
    game = played(8, (8, 1, 1))
    actual = settle(game, points=start, regular_route=RewardRoute.HILL_FIRST)
    assert actual.hill == (0, 0, 0)
    assert actual.pool == (3, 0, 0)
    assert settle(game, points=start, regular_route=RewardRoute.POOL).pool[0] == 6


def test_assistance_prefers_fuller_unclosed_pool():
    start = ledger(pool=(20, 17, 15))
    state = settle(played(6, (7, 2, 1)), points=start)
    assert state.pool == (20, 19, 15)
    assert state.vists[0][1] == 20


def test_equal_pool_help_splits_even_amount():
    start = ledger(pool=(20, 15, 15))
    state = settle(played(7, (7, 2, 1)), points=start)
    assert state.pool == (20, 17, 17)
    assert state.vists[0][1:] == (20, 20)


def test_equal_pool_help_odd_point_creates_two_five_vists():
    start = ledger(pool=(20, 15, 15))
    state = settle(played(10, (10, 0, 0)), points=start)
    assert state.pool == (20, 20, 20)
    assert state.vists[0][1:] == (50, 50)
    # 10 points exactly fill both. Test the actual odd-remainder case separately.
    start = ledger(pool=(20, 17, 17))
    state = settle(played(8, (8, 1, 1)), points=start)
    assert state.vists[0][1:] == (30, 30)
    start = ledger(pool=(20, 19, 19))
    state = settle(played(7, (7, 2, 1)), points=start)
    assert state.vists[0][1:] == (20, 20)  # 10 help + 10 surplus


def test_one_odd_help_point_does_not_change_pools():
    start = ledger(pool=(20, 15, 15), hill=(1, 0, 0))
    state = settle(played(6, (6, 2, 2)), points=start, regular_route=RewardRoute.HILL_FIRST)
    assert state.hill[0] == 0
    assert state.pool == (20, 15, 15)
    assert state.vists[0][1:] == (5, 5)


def test_last_deal_excess_gets_five_per_opponent():
    start = ledger(pool=(18, 20, 20))
    state = settle(played(8, (8, 1, 1)), points=start)
    assert state.pool == (20, 20, 20)
    assert state.vists[0][1:] == (20, 20)
    assert state.closed


def test_all_closed_rejects_new_deal():
    finished = settle(played(8, (8, 1, 1)), points=ledger(pool=(18, 20, 20)))
    with pytest.raises(RuleViolation):
        settle_game(finished, played(), "new")


def test_passout_hill_and_zero_trick_bonus_and_cycle():
    state = settle(passouts((5, 5, 0)))
    assert state.hill == (5, 5, 0)
    assert state.pool == (0, 0, 1)
    assert state.passout_level == 7


def test_passout_bonus_mandatory_pool_closure_then_hill_or_help():
    game = passouts((0, 4, 6), level=8)
    start = ledger(pool=(19, 20, 20), hill=(2, 0, 0), passout=8)
    hill_route = settle(
        game,
        points=start,
        passout_routes=(RewardRoute.HILL_FIRST, RewardRoute.POOL, RewardRoute.POOL),
    )
    help_route = settle(
        game, points=start, passout_routes=(RewardRoute.HELP, RewardRoute.POOL, RewardRoute.POOL)
    )
    assert hill_route.pool == (20, 20, 20)
    assert hill_route.hill == (0, 12, 18)
    assert hill_route.passout_level == 6
    assert help_route.hill[0] == 2
    assert help_route.vists[0][1:] == (10, 10)


def test_passout_bonus_closed_pool_mandatory_hill_then_help():
    game = passouts((0, 4, 6), level=8)
    start = ledger(pool=(20, 20, 19), hill=(2, 0, 0), passout=8)
    state = settle(game, points=start)
    assert state.hill[0] == 0
    assert state.vists[0][2] == 10


def test_passout_bonus_insufficient_pool_can_pay_hill():
    game = passouts((0, 4, 6), level=7)
    start = ledger(pool=(10, 20, 20), hill=(2, 0, 0), passout=7)
    state = settle(
        game,
        points=start,
        passout_routes=(RewardRoute.HILL_FIRST, RewardRoute.POOL, RewardRoute.POOL),
    )
    assert state.hill[0] == 0
    assert state.pool[0] == 10


def test_two_passout_zero_players_require_explicit_order():
    game = passouts((0, 0, 10))
    with pytest.raises(RuleViolation, match="Explicit reward order"):
        settle(game)
    state = settle(game, passout_reward_order=(0, 1))
    assert state.pool == (1, 1, 0)
    with pytest.raises(RuleViolation):
        settle(game, passout_reward_order=([0], 1))
    assert state.hill == (0, 0, 10)


def test_passout_level_does_not_reset_on_contract_loss_or_concession():
    start = ledger(passout=7)
    game = replace(played(8, (7, 2, 1)), passout_level=7)
    assert settle(game, points=start).passout_level == 7
    start = ledger(passout=8)
    game = replace(played(8, (8, 1, 1)), passout_level=8)
    assert settle(game, points=start).passout_level == 6


def test_duplicate_deal_and_version_rejected():
    game = played()
    state = settle(game)
    with pytest.raises(RuleViolation, match="only be settled once"):
        settle_game(state, game, "d1")
    with pytest.raises(RuleViolation, match="Stale"):
        settle_game(state, game, "d2", expected_version=0)


def test_ledger_event_fields_are_secret_free_and_ordered():
    state = settle(played())
    assert tuple(e.sequence for e in state.entries) == tuple(range(1, len(state.entries) + 1))
    assert all(e.deal_id == "d1" and e.amount > 0 for e in state.entries)
    assert state.version == 1
    assert set(e.reason for e in state.entries) >= {"contract_shortfall", "consolation"}


def test_invalid_finished_results_rejected_without_mutation():
    base = ledger()
    game = played()
    bad = replace(game, tricks_won=(8, 3, 2))
    with pytest.raises(RuleViolation):
        settle_game(base, bad, "d1")
    assert base == ledger()
