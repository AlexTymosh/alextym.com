"""Deterministic fuzz-like regression without additional dependencies."""

from __future__ import annotations

import random

import pytest

from preferans.domain import (
    AuctionAction,
    Bid,
    DefenseDecision,
    Phase,
    Suit,
    auction_action,
    deal,
    decide_defense,
    declare_contract,
    discard_cards,
    legal_play_cards,
    play_card,
    shuffled_deck,
    start_game,
)


@pytest.mark.parametrize("seed", range(50))
def test_passout_plays_thirty_distinct_cards(seed: int) -> None:
    random_source = random.Random(seed)
    dealer = seed % 3
    game = start_game(deal(shuffled_deck(random_source), dealer), passout_level=6 + seed % 3)
    first = game.first_hand
    for actor in (first, (first + 1) % 3, (first + 2) % 3):
        game = auction_action(game, actor, AuctionAction.pass_turn())
    assert game.phase == Phase.PLAY
    played = []
    for _ in range(30):
        owner = game.turn
        assert owner is not None
        options = legal_play_cards(game, owner)
        assert options
        selected = random_source.choice(options)
        played.append(selected)
        game = play_card(game, owner, selected)
    assert game.phase == Phase.FINISHED
    assert len(set(played)) == 30
    assert set(played).isdisjoint(game.widow)
    assert sum(game.tricks_won) == 10


@pytest.mark.parametrize("seed", range(50))
def test_mandatory_six_spades_plays_valid_full_deal(seed: int) -> None:
    rng = random.Random(seed + 300)
    dealer = seed % 3
    game = start_game(deal(shuffled_deck(rng), dealer))
    declarer = game.first_hand
    game = auction_action(game, declarer, AuctionAction.place(Bid.regular(6, Suit.SPADES)))
    for actor in ((declarer + 1) % 3, (declarer + 2) % 3):
        game = auction_action(game, actor, AuctionAction.pass_turn())
    game = discard_cards(game, declarer, (game.widow[0], game.widow[1]))
    game = declare_contract(game, declarer, Bid.regular(6, Suit.SPADES))
    assert game.phase == Phase.PLAY
    for _ in range(30):
        owner = game.turn
        assert owner is not None
        game = play_card(game, owner, rng.choice(legal_play_cards(game, owner)))
    assert game.phase == Phase.FINISHED
    assert len(game.completed_tricks) == 10
    assert sum(game.tricks_won) == 10
    assert set(game.discarded) == set(game.widow)


@pytest.mark.parametrize("seed", range(25))
def test_no_widow_ten_can_complete_with_both_visting(seed: int) -> None:
    rng = random.Random(600 + seed)
    game = start_game(deal(shuffled_deck(rng), seed % 3))
    declarer = game.first_hand
    game = auction_action(game, declarer, AuctionAction.place(Bid.ten_no_widow(None)))
    for actor in ((declarer + 1) % 3, (declarer + 2) % 3):
        game = auction_action(game, actor, AuctionAction.pass_turn())
    game = declare_contract(game, declarer, Bid.ten_no_widow(None))
    game = decide_defense(game, (declarer + 1) % 3, DefenseDecision.VIST)
    game = decide_defense(game, (declarer + 2) % 3, DefenseDecision.VIST)
    assert game.widow_revealed == 0
    for _ in range(30):
        owner = game.turn
        assert owner is not None
        game = play_card(game, owner, rng.choice(legal_play_cards(game, owner)))
    assert game.phase == Phase.FINISHED
    assert game.widow_revealed == 0
    assert sum(game.tricks_won) == 10
