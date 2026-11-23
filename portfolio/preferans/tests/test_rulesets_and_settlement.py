"""Immutable ruleset, exact hill rounding, zero sum and punishment tests."""

import random
from dataclasses import replace

import pytest

from preferans.domain import (
    Ruleset,
    ScoreState,
    freeze_ruleset,
)
from preferans.domain.settlement import (
    discard_sheet_penalties,
    discard_sheet_placements,
    final_hill_vists,
    net_results,
    pair_punishments,
    placements,
)


def test_ruleset_snapshot_is_stable_and_content_addressed():
    rules = Ruleset()
    a, b = freeze_ruleset(rules), freeze_ruleset(rules)
    assert a == b
    assert len(a.sha256) == 64
    other = freeze_ruleset(replace(rules, pool_target=30, version=2))
    assert a.sha256 != other.sha256
    assert a.rules.pool_target == 20


@pytest.mark.parametrize(
    "data",
    [
        {"version": True},
        {"pool_target": 0},
        {"pool_target": 2.5},
        {"regular_costs": (2, 4, 6, 8)},
        {"misere_cost": -1},
        {"double_personal_required": (2, 1, 2)},
        {"hill_vist_denominator": 0},
        {"identifier": ""},
    ],
)
def test_invalid_rulesets_rejected(data):
    with pytest.raises(ValueError):
        Ruleset(**data)


def test_modified_versioned_cost_is_used_not_global_default():
    a = Ruleset(version=2, regular_costs=(3, 5, 7, 9, 11))
    assert a.cost(8) == 7
    assert Ruleset().cost(8) == 6


@pytest.mark.parametrize(("hill", "wists"), [(1, 3), (2, 7), (3, 10), (6, 20)])
def test_rounding_whole_hill_once(hill, wists):
    state = replace(ScoreState.new(), hill=(hill, 0, 0))
    assert final_hill_vists(state) == (wists, 0, 0)


def test_golden_results_for_two_hills():
    state = replace(ScoreState.new(), hill=(2, 0, 0))
    assert net_results(state) == (-14, 7, 7)
    state = replace(ScoreState.new(), hill=(0, 3, 6))
    assert net_results(state) == (30, 0, -30)


def test_directed_wists_change_balances_but_remain_zero_sum():
    state = replace(ScoreState.new(), vists=((0, 8, 4), (0, 0, 0), (0, 0, 0)))
    assert net_results(state) == (12, -8, -4)


def test_randomized_hill_and_directed_vists_are_zero_sum():
    rng = random.Random(20261123)
    for _ in range(400):
        hills = tuple(rng.randrange(0, 1000) for _ in range(3))
        vists = tuple(
            tuple(0 if i == j else rng.randrange(0, 100000) for j in range(3)) for i in range(3)
        )
        state = replace(ScoreState.new(), hill=hills, vists=vists)
        assert sum(net_results(state)) == 0


def test_places_and_ties():
    assert placements((30, 0, -30)) == (1, 2, 3)
    assert placements((10, 10, -20)) == (1, 1, 3)
    assert placements((20, -10, -10)) == (1, 2, 2)
    assert placements((0, 0, 0)) == (None, None, None)


def test_pair_punishment_round_up_each_pair():
    awards = pair_punishments((100, 0, -451))
    assert [(a.winner, a.loser, a.ordinary_units) for a in awards] == [
        (0, 1, 2),
        (0, 2, 12),
        (1, 2, 10),
    ]
    assert awards[1].bare == 1 and awards[1].ordinary == 2
    assert awards[2].bare == 1 and awards[2].ordinary == 0
    assert pair_punishments((0, 0, 0)) == ()
    assert pair_punishments((100, 100, -1))[0].winner == 0
    assert pair_punishments((100, 100, -1))[0].loser == 2


def test_bare_can_be_exchanged_for_ten_ordinary():
    bare = pair_punishments((501, 0, 0))
    ordinary = pair_punishments((501, 0, 0), prefer_bare=False)
    assert bare[0].bare == 1 and bare[0].ordinary == 1
    assert ordinary[0].bare == 0 and ordinary[0].ordinary == 11


def test_voluntary_sheet_discard_distinct_from_normal_results():
    awards = discard_sheet_penalties(1)
    assert {(x.winner, x.loser, x.bare) for x in awards} == {(0, 1, 1), (2, 1, 1)}
    assert discard_sheet_placements(1) == (1, 3, 1)


def test_score_state_rejects_invalid_values():
    for overrides in (
        {"pool": (21, 0, 0)},
        {"hill": (-1, 0, 0)},
        {"vists": ((1, 0, 0), (0, 0, 0), (0, 0, 0))},
        {"version": 1},
        {"closed": True},
        {"passout_level": 9},
    ):
        with pytest.raises(ValueError):
            replace(ScoreState.new(), **overrides)
