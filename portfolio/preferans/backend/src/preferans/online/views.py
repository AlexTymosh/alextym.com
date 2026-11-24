"""Explicitly allow-listed client projections. Never serialize GameState itself."""

from __future__ import annotations

from preferans.domain.auction import (
    Bid,
    can_say_here,
    legal_auction_bids,
    legal_final_contracts,
)
from preferans.domain.cards import Card
from preferans.domain.game import GameState, Phase, legal_play_cards
from preferans.domain.ledger import ScoreState
from preferans.online.controls import public_controls
from preferans.online.deal_flow import projection as next_deal_projection


def public_bid(bid: Bid | None) -> dict | None:
    if bid is None:
        return None
    return {
        "kind": bid.kind.value,
        "level": bid.level,
        "suit": bid.suit.value if bid.suit else None,
    }


def public_card(card: Card) -> dict:
    return {"suit": card.suit.value, "rank": card.rank.value}


def seat_view(
    room: dict,
    state: GameState | None,
    score: ScoreState | None,
    uid: str,
    version: int,
    *,
    owner: bool = False,
    controls: dict | None = None,
    now_ms: int = 0,
) -> dict:
    seats = room["seats"]
    my_seat = seats.index(uid) if uid in seats else None
    result = {
        "room_id": room["id"],
        "version": version,
        "status": room["status"],
        "occupied": [bool(x) for x in seats],
        "my_seat": my_seat,
        "room_admin": owner or uid == room["admin_uid"],
        "game_id": room.get("game_id"),
        "controls": public_controls(controls or {}, now_ms, my_seat),
    }
    if room["status"] == "between":
        clock = next_deal_projection(controls or {}, room.get("game_id"))
        if clock is not None:
            result["next_deal"] = clock
    if state is None:
        setup = room.get("lobby_setup")
        if room["status"] == "lobby" and setup is not None and score is not None:
            result["lobby_setup"] = {
                "ready": list(setup["ready"]),
                "dealer": setup["dealer"],
                "target": score.target,
                "ruleset": score.ruleset.rules.identifier,
                "ruleset_version": score.ruleset.rules.version,
            }
        return result
    exposed = [
        {"seat": i, "cards": [public_card(c) for c in state.hands[i]]}
        for i in sorted(state.exposed_hands)
    ]
    # Auction history is public. Retain only the last call per seat, never
    # serialize the state or a player's private discard.
    calls = [None, None, None]
    high = None
    for event in state.auction.history:
        action = event.action
        if action.bid is not None:
            high = action.bid
        calls[event.actor] = {
            "kind": action.kind.value,
            "bid": public_bid(high if action.kind.value == "here" else action.bid),
        }
    result.update(
        {
            "phase": state.phase.value,
            "turn": state.turn,
            "controller": state.controllers[state.turn] if state.turn is not None else None,
            "dealer": state.dealer,
            "first_hand": state.first_hand,
            "is_passout": state.is_passout,
            "played_tricks": len(state.completed_tricks),
            "declarer": state.declarer,
            "contract": public_bid(state.contract),
            "high_bid": public_bid(state.auction.high_bid),
            "auction_calls": calls,
            "last_trick_winner": state.completed_tricks[-1].winner
            if state.completed_tricks
            else None,
            "tricks_won": list(state.tricks_won),
            "hand_counts": [len(h) for h in state.hands],
            "open_hands": exposed,
            "trick": [
                {"owner": play.owner, "card": public_card(play.card)} for play in state.trick
            ],
            "last_trick": [
                {"owner": play.owner, "card": public_card(play.card)}
                for play in state.completed_tricks[-1].cards
            ]
            if state.completed_tricks
            else [],
            "widow": [public_card(card) for card in state.widow[: state.widow_revealed]],
            "defense": [d.value if d else None for d in state.defense],
            "end_reason": state.end_reason.value if state.end_reason else None,
            "mode": state.mode.value if state.mode else None,
        }
    )
    if my_seat is not None:
        result["hand"] = [public_card(card) for card in state.hands[my_seat]]
        result["legal_cards"] = (
            [public_card(c) for c in legal_play_cards(state, state.turn)]
            if state.phase in (Phase.PLAY, Phase.OPENING_LEAD)
            and state.turn is not None
            and state.controllers[state.turn] == my_seat
            else []
        )
        result["legal_bids"] = (
            [public_bid(b) for b in legal_auction_bids(state.auction, my_seat)]
            if state.phase == Phase.AUCTION
            else []
        )
        result["can_say_here"] = state.phase == Phase.AUCTION and can_say_here(
            state.auction, my_seat
        )
        result["legal_contracts"] = (
            [public_bid(b) for b in legal_final_contracts(state.winning_bid)]
            if state.phase == Phase.DECLARE
            and my_seat == state.declarer
            and state.winning_bid is not None
            else []
        )
    if score is not None:
        result["score"] = {
            "pool": list(score.pool),
            "hill": list(score.hill),
            "vists": [list(row) for row in score.vists],
            "passout_level": score.passout_level,
            "closed": score.closed,
            "ruleset_hash": score.ruleset.sha256,
            "target": score.target,
        }
    return result
