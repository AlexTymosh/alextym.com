"""PR30: success proposals, retired reveal state, and repeated final review."""

from dataclasses import replace

import pytest

from preferans.domain.auction import Bid, RuleViolation
from preferans.domain.game import (
    EndReason,
    Phase,
    can_offer_misere,
    declare_contract,
    legal_play_cards,
    offer_misere,
    play_card,
    vote_misere,
)
from preferans.domain.ledger import ScoreState
from preferans.domain.scoring import RewardRoute, settle_game
from preferans.domain.settlement import final_hill_vists, pairwise_results
from preferans.online import store
from preferans.online.codec import decode, encode
from preferans.online.pause_clock import retire_reveal
from preferans.online.views import seat_view
from test_history_ranking import complete_score, session
from test_pr21_misere_here import ready
from test_scoring import ledger, passouts, played
from test_secure_rooms import FakeDB


@pytest.mark.parametrize("initiator", [0, 1, 2])
def test_play_misere_offer_requires_only_two_defenders(initiator):
    state = declare_contract(ready(), 0, Bid.misere())
    state = play_card(state, state.turn, legal_play_cards(state, state.turn)[0])
    offer = offer_misere(state, initiator)
    assert offer.phase == Phase.MISERE_OFFER
    assert offer.misere_votes == (frozenset() if initiator == 0 else {initiator})
    assert offer.trick == state.trick and not legal_play_cards(offer, 1)
    assert decode(encode(offer)) == offer
    with pytest.raises(RuleViolation):
        vote_misere(offer, 0, True)
    for defender in sorted({1, 2} - offer.misere_votes):
        offer = vote_misere(offer, defender, True)
    assert offer.end_reason == EndReason.MISERE_ACCEPTED
    assert offer.completed_tricks == state.completed_tricks
    assert offer.tricks_won == state.tricks_won and not offer.trick
    assert settle_game(ScoreState.new(), offer, "success").pool == (10, 0, 0)


def test_rejected_defender_proposal_restores_partial_play():
    state = declare_contract(ready(), 0, Bid.misere())
    state = play_card(state, state.turn, legal_play_cards(state, state.turn)[0])
    refused = vote_misere(offer_misere(state, 2), 1, False)
    assert replace(refused, misere_refused_at=None) == state
    assert not can_offer_misere(refused, 0)
    assert not can_offer_misere(replace(state, tricks_won=(1, 0, 0)), 1)


def test_ordinary_and_passout_open_pool_reject_hill_route():
    score = ledger(pool=(10, 15, 10), hill=(3, 0, 0))
    game = played(7, (7, 2, 1))
    with pytest.raises(RuleViolation):
        settle_game(score, game, "invalid", regular_route=RewardRoute.HILL_FIRST)
    assert settle_game(score, game, "valid").pool[0] == 14
    game = passouts((0, 4, 6))
    with pytest.raises(RuleViolation):
        settle_game(
            score,
            game,
            "invalid-passout",
            passout_routes=(RewardRoute.HILL_FIRST, RewardRoute.POOL, RewardRoute.POOL),
        )
    assert settle_game(score, game, "valid-passout").hill[0] == 3


def test_final_hill_distribution_is_projection_only():
    game = vote_misere(vote_misere(offer_misere(ready(), 0), 1, True), 2, True)
    score = replace(
        ScoreState.new(),
        pool=(20, 20, 20),
        hill=(0, 3, 6),
        closed=True,
        vists=((0, 8, 4), (0, 0, 0), (0, 0, 0)),
    )
    room = {
        "id": "a" * 32,
        "status": "awaiting_settlement",
        "seats": ["a", "b", "c"],
        "admin_uid": "a",
        "game_id": "g",
    }
    view = seat_view(room, game, score, "a", 1)
    assert view["final_hill_vists"] == list(final_hill_vists(score)) == [0, 10, 20]
    assert view["final_settlement"]["pairs"] == [list(row) for row in pairwise_results(score)]
    assert score.vists == ((0, 8, 4), (0, 0, 0), (0, 0, 0))
    assert "final_hill_vists" not in seat_view(room, game, score, "observer", 1, owner=True)


def test_two_final_review_corrections_before_confirmation(monkeypatch):
    monkeypatch.setenv("PREFERANS_REALTIME_ENABLED", "false")
    monkeypatch.setattr(store, "settle_game", lambda *_a, **_kw: complete_score(hill=(0, 300, 0)))
    db = FakeDB()
    api, rid = session(db, [1_800_000_000_000])
    api.settle(
        rid,
        "auth-A",
        "pr30-settle",
        api.view(rid, "auth-A")["version"],
        {"regular_route": "pool", "passout_routes": ["pool"] * 3},
        False,
    )
    before = api.view(rid, "auth-A")
    assert before["final_review"]
    for n, delta in enumerate((2, -1)):
        view = api.view(rid, "auth-A")
        args = {
            "field": "hill",
            "seat": 1,
            "against": None,
            "delta": delta,
            "reason": "Test correction",
        }
        api.admin_adjust(rid, "auth-A", f"pr30-adjust-{n}", view["version"], args, False)
    after = api.view(rid, "auth-A")
    assert after["final_review"] and after["score"]["hill"][1] == before["score"]["hill"][1] + 1
    assert len(after["controls"]["adjustments"]) == 2
    assert f"preferans_results/{rid}" not in db.docs
    api.command(rid, "auth-A", "pr30-confirm", after["version"], "final_confirm", {})
    assert api.view(rid, "auth-A")["status"] == "closed"


def test_retire_legacy_reveal_preserves_unrelated_pause():
    control = {
        "reveal": {"id": 1},
        "revealed_cards": [{}],
        "pause_reasons": ["accidental_reveal", "connection_lost"],
        "paused_at": 10,
    }
    assert retire_reveal(control, 20)
    assert control["pause_reasons"] == ["connection_lost"] and control["paused_at"] == 10
    assert "reveal" not in control and "revealed_cards" not in control
    assert not retire_reveal(control, 30)
