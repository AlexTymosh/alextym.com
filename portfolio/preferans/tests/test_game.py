from __future__ import annotations

import pytest

from preferans.domain import (
    AuctionAction,
    Bid,
    DefenseDecision,
    DefenseMode,
    EndReason,
    FULL_DECK,
    Phase,
    RuleViolation,
    Suit,
    auction_action,
    choose_defense_mode,
    deal,
    decide_defense,
    declare_contract,
    discard_cards,
    legal_play_cards,
    play_card,
    start_game,
)


B = AuctionAction.place
P = AuctionAction.pass_turn()


def build_game(dealer: int = 0, passout_level: int = 6):
    return start_game(deal(FULL_DECK, dealer), passout_level)


def win_first_hand(bid: Bid):
    game = build_game()
    game = auction_action(game, 1, B(bid))
    game = auction_action(game, 2, P)
    game = auction_action(game, 0, P)
    assert game.declarer == 1
    return game


def ready_regular(bid: Bid = Bid.regular(7, Suit.CLUBS), contract: Bid | None = None):
    game = win_first_hand(bid)
    game = discard_cards(game, 1, (game.hands[1][0], game.widow[0]))
    game = declare_contract(game, 1, contract or bid)
    return game


def complete_with_legal_cards(game):
    count = 0
    while game.phase == Phase.PLAY:
        owner = game.turn
        assert owner is not None
        choices = legal_play_cards(game, owner)
        assert choices
        game = play_card(game, game.controllers[owner], choices[0], owner=owner)
        count += 1
        assert count <= 30
    assert game.phase == Phase.FINISHED
    assert len(game.completed_tricks) == 10
    assert sum(game.tricks_won) == 10
    assert sum(map(len, game.hands)) == 0
    return game


def test_winning_regular_bid_enters_discard_without_final_contract() -> None:
    game = win_first_hand(Bid.regular(7, Suit.CLUBS))
    assert game.phase == Phase.DISCARD
    assert game.contract is None
    assert game.widow_revealed == 2
    assert game.auction.high_bid == Bid.regular(7, Suit.CLUBS)
    before = game
    with pytest.raises(RuleViolation):
        discard_cards(game, 0, (game.widow[0], game.widow[1]))
    assert game == before


def test_discard_is_private_and_final_contract_may_increase() -> None:
    game = win_first_hand(Bid.regular(7, Suit.CLUBS))
    discarded = (game.hands[1][0], game.widow[1])
    game = discard_cards(game, 1, discarded)
    assert game.phase == Phase.DECLARE
    assert len(game.hands[1]) == 10
    assert game.discarded == discarded
    with pytest.raises(RuleViolation):
        declare_contract(game, 1, Bid.regular(7, Suit.SPADES))
    with pytest.raises(RuleViolation):
        declare_contract(game, 1, Bid.misere())
    game = declare_contract(game, 1, Bid.regular(8, Suit.SPADES))
    assert game.contract == Bid.regular(8, Suit.SPADES)
    assert game.phase == Phase.DEFENSE_FIRST
    assert game.turn == 2


def test_wrong_discard_or_duplicate_card_never_mutates_state() -> None:
    game = win_first_hand(Bid.regular(6, Suit.HEARTS))
    with pytest.raises(RuleViolation):
        discard_cards(game, 1, (game.hands[1][0], game.hands[1][0]))
    with pytest.raises(RuleViolation):
        discard_cards(game, 1, (game.hands[0][0], game.widow[1]))
    assert len(game.hands[1]) == 10 and game.discarded == ()


def test_no_widow_ten_does_not_reveal_widow_and_can_raise_suit() -> None:
    game = win_first_hand(Bid.ten_no_widow(Suit.CLUBS))
    assert game.phase == Phase.DECLARE
    assert game.widow_revealed == 0
    assert game.discarded == ()
    with pytest.raises(RuleViolation):
        declare_contract(game, 1, Bid.ten_no_widow(Suit.SPADES))
    with pytest.raises(RuleViolation):
        declare_contract(game, 1, Bid.regular(10, None))
    game = declare_contract(game, 1, Bid.ten_no_widow(Suit.HEARTS))
    assert game.widow_revealed == 0
    assert game.phase == Phase.DEFENSE_FIRST


def test_misere_without_widow_reveals_defenders_before_their_first_lead() -> None:
    game = build_game()
    game = auction_action(game, 1, B(Bid.misere()))
    game = auction_action(game, 2, B(Bid.regular(9, Suit.SPADES)))
    game = auction_action(game, 0, P)
    game = auction_action(game, 1, B(Bid.misere_no_widow()))
    game = auction_action(game, 2, P)
    assert game.phase == Phase.DECLARE
    assert game.widow_revealed == 0
    game = declare_contract(game, 1, Bid.misere_no_widow())
    assert game.phase == Phase.PLAY
    assert game.exposed_hands == frozenset()
    first_card = legal_play_cards(game, 1)[0]
    game = play_card(game, 1, first_card)
    assert game.exposed_hands == frozenset((0, 2))
    assert game.widow_revealed == 0


def test_normal_misere_discard_and_first_defender_lead_exposes_both_defenders() -> None:
    game = build_game(dealer=2)
    # first hand 0 passes, seat 1 declares misere, seat 2 passes, seat 0 already passed
    game = auction_action(game, 0, P)
    game = auction_action(game, 1, B(Bid.misere()))
    game = auction_action(game, 2, P)
    assert game.declarer == 1
    assert game.phase == Phase.DISCARD
    game = discard_cards(game, 1, tuple(game.widow))
    game = declare_contract(game, 1, Bid.misere())
    assert game.phase == Phase.PLAY and game.turn == 0
    assert game.exposed_hands == frozenset((0, 2))


def test_six_spades_mandates_both_defenders_and_is_closed() -> None:
    game = ready_regular(Bid.regular(6, Suit.SPADES))
    assert game.phase == Phase.PLAY
    assert game.defense[0] == game.defense[2] == DefenseDecision.VIST
    assert game.mode is None and game.exposed_hands == frozenset()
    with pytest.raises(RuleViolation):
        decide_defense(game, 0, DefenseDecision.PASS)
    complete_with_legal_cards(game)


def test_first_defender_may_not_half_vist() -> None:
    game = ready_regular()
    with pytest.raises(RuleViolation):
        decide_defense(game, 2, DefenseDecision.HALF)
    with pytest.raises(RuleViolation):
        decide_defense(game, 0, DefenseDecision.VIST)


@pytest.mark.parametrize("level", [6, 7])
def test_first_pass_second_half_and_first_confirms_pass_finishes(level: int) -> None:
    game = ready_regular(Bid.regular(level, Suit.CLUBS))
    game = decide_defense(game, 2, DefenseDecision.PASS)
    game = decide_defense(game, 0, DefenseDecision.HALF)
    assert game.phase == Phase.DEFENSE_RECONSIDER and game.turn == 2
    game = decide_defense(game, 2, DefenseDecision.PASS)
    assert game.phase == Phase.FINISHED
    assert game.end_reason == EndReason.HALF_VIST
    assert game.half_vist_receiver == 0


def test_first_reclaims_vist_and_second_must_pass() -> None:
    game = ready_regular()
    game = decide_defense(game, 2, DefenseDecision.PASS)
    game = decide_defense(game, 0, DefenseDecision.HALF)
    game = decide_defense(game, 2, DefenseDecision.VIST)
    assert game.defense[0] == DefenseDecision.PASS
    assert game.defense[2] == DefenseDecision.VIST
    assert game.phase == Phase.OPENING_LEAD
    assert game.turn == 1


def test_two_passes_end_deal_and_only_six_seven_credit_half_vist() -> None:
    for level, expected_receiver in ((6, 0), (7, 0), (8, None), (9, None), (10, None)):
        game = ready_regular(Bid.regular(level, Suit.HEARTS))
        game = decide_defense(game, 2, DefenseDecision.PASS)
        game = decide_defense(game, 0, DefenseDecision.PASS)
        assert game.phase == Phase.FINISHED
        assert game.end_reason == EndReason.ALL_PASSED
        assert game.half_vist_receiver == expected_receiver
        assert game.completed_tricks == ()


def test_half_vist_not_offered_on_eight_or_when_first_vists() -> None:
    game = ready_regular(Bid.regular(8, Suit.CLUBS))
    game = decide_defense(game, 2, DefenseDecision.PASS)
    with pytest.raises(RuleViolation):
        decide_defense(game, 0, DefenseDecision.HALF)
    game2 = ready_regular()
    game2 = decide_defense(game2, 2, DefenseDecision.VIST)
    with pytest.raises(RuleViolation):
        decide_defense(game2, 0, DefenseDecision.HALF)


def test_two_vists_play_closed() -> None:
    game = ready_regular()
    game = decide_defense(game, 2, DefenseDecision.VIST)
    game = decide_defense(game, 0, DefenseDecision.VIST)
    assert game.phase == Phase.PLAY and game.exposed_hands == frozenset()
    assert game.controllers == (0, 1, 2)
    complete_with_legal_cards(game)


def test_single_vist_declarer_first_leads_before_mode_selection() -> None:
    game = ready_regular()
    game = decide_defense(game, 2, DefenseDecision.PASS)
    game = decide_defense(game, 0, DefenseDecision.VIST)
    assert game.phase == Phase.OPENING_LEAD
    assert game.turn == 1
    first_card = legal_play_cards(game, 1)[0]
    game = play_card(game, 1, first_card)
    assert game.phase == Phase.CHOOSE_MODE and game.turn == 0
    with pytest.raises(RuleViolation):
        choose_defense_mode(game, 2, DefenseMode.OPEN)
    game = choose_defense_mode(game, 0, DefenseMode.OPEN)
    assert game.phase == Phase.PLAY and game.turn == 2
    assert game.controllers[2] == 0 and game.exposed_hands == frozenset((2,))
    played = legal_play_cards(game, 2)[0]
    with pytest.raises(RuleViolation):
        play_card(game, 2, played, owner=2)
    game = play_card(game, 0, played, owner=2)
    assert game.trick[-1].actor == 0 and game.trick[-1].owner == 2
    assert len(game.trick) == 2


def test_single_vist_when_defender_leads_selects_mode_before_first_card() -> None:
    game = build_game()
    game = auction_action(game, 1, P)
    game = auction_action(game, 2, P)
    game = auction_action(game, 0, B(Bid.regular(7, Suit.CLUBS)))
    assert game.declarer == 0
    game = discard_cards(game, 0, tuple(game.widow))
    game = declare_contract(game, 0, Bid.regular(7, Suit.CLUBS))
    game = decide_defense(game, 1, DefenseDecision.VIST)
    game = decide_defense(game, 2, DefenseDecision.PASS)
    assert game.phase == Phase.CHOOSE_MODE and game.turn == 1
    game = choose_defense_mode(game, 1, DefenseMode.CLOSED)
    assert game.turn == game.first_hand == 1
    assert game.exposed_hands == frozenset()
    complete_with_legal_cards(game)


def test_all_passouts_reveal_widow_progressively_and_first_three_leads_from_first_hand() -> None:
    game = build_game(passout_level=8)
    for seat in (1, 2, 0):
        game = auction_action(game, seat, P)
    assert game.is_passout and game.phase == Phase.PLAY
    assert game.widow_revealed == 1
    for trick_number in range(1, 11):
        if trick_number <= 3:
            assert game.turn == game.first_hand
        else:
            assert game.turn == game.completed_tricks[-1].winner
        for _ in range(3):
            owner = game.turn
            assert owner is not None
            legal = legal_play_cards(game, owner)
            assert legal
            if trick_number <= 2:
                force = game.widow[trick_number - 1].suit
                if any(c.suit == force for c in game.hands[owner]):
                    assert all(c.suit == force for c in legal)
            game = play_card(game, owner, legal[0])
        if trick_number == 1:
            assert game.widow_revealed == 2
    assert game.phase == Phase.FINISHED
    assert game.end_reason == EndReason.PLAYED
    assert sum(game.tricks_won) == 10
    assert all(not h for h in game.hands)


def test_illegal_card_rejected_without_state_mutation() -> None:
    game = ready_regular(Bid.regular(6, Suit.SPADES))
    owner = game.turn
    assert owner is not None
    other_card = game.hands[(owner + 1) % 3][0]
    with pytest.raises(RuleViolation):
        play_card(game, owner, other_card)
    assert game.trick == () and all(len(hand) == 10 for hand in game.hands)


def test_full_replay_uses_pure_functions_without_io() -> None:
    deck = FULL_DECK
    a = start_game(deal(deck, 0))
    b = start_game(deal(deck, 0))
    actions = ((1, B(Bid.regular(6, Suit.SPADES))), (2, P), (0, P))
    for seat, action in actions:
        a, b = auction_action(a, seat, action), auction_action(b, seat, action)
        assert a == b
    for game in (a, b):
        assert game.phase == Phase.DISCARD
    discard = (a.hands[1][0], a.widow[0])
    a, b = discard_cards(a, 1, discard), discard_cards(b, 1, discard)
    a = declare_contract(a, 1, Bid.regular(6, Suit.SPADES))
    b = declare_contract(b, 1, Bid.regular(6, Suit.SPADES))
    for _ in range(30):
        actor = a.turn
        assert actor is not None and a == b
        card = legal_play_cards(a, actor)[0]
        a, b = play_card(a, actor, card), play_card(b, actor, card)
    assert a == b and a.phase == Phase.FINISHED
    assert sum(a.tricks_won) == 10


def test_deal_stays_immutable_when_next_state_is_created() -> None:
    before = build_game()
    after = auction_action(before, 1, B(Bid.regular(8, Suit.HEARTS)))
    assert before.auction.high_bid is None
    assert before.phase == Phase.AUCTION
    assert after.auction.high_bid == Bid.regular(8, Suit.HEARTS)
    assert before.hands == after.hands
