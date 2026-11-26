"""Randomized immutable settlement and conservation invariants."""

import random
from dataclasses import replace

from preferans.domain import RewardRoute, ScoreState, settle_game
from preferans.domain.settlement import net_results
from test_scoring import played


def test_400_randomized_settlements_are_integer_and_zero_sum():
    rng = random.Random(1097)
    for n in range(400):
        level = rng.randrange(6, 11)
        declarer_tricks = rng.randrange(0, 11)
        first = rng.randrange(0, 11 - declarer_tricks)
        tricks = (declarer_tricks, first, 10 - declarer_tricks - first)
        source = played(level=level, tricks=tricks)
        pool = tuple(rng.randrange(0, 21) for _ in range(3))
        if pool == (20, 20, 20):
            pool = (19, 20, 20)
        hill = tuple(rng.randrange(0, 40) for _ in range(3))
        initial = replace(ScoreState.new(), pool=pool, hill=hill, closed=all(v == 20 for v in pool))
        old_pool, old_hill = initial.pool, initial.hill
        actual = settle_game(
            initial,
            source,
            f"random-{n}",
            regular_route=RewardRoute.HILL_FIRST
            if n % 2 and initial.pool[0] == initial.target
            else RewardRoute.POOL,
        )
        assert initial.pool == old_pool and initial.hill == old_hill
        assert all(isinstance(v, int) and 0 <= v <= 20 for v in actual.pool)
        assert all(isinstance(v, int) and v >= 0 for v in actual.hill)
        assert sum(net_results(actual)) == 0
        assert actual.version == 1
        assert len(actual.deal_ids) == 1
