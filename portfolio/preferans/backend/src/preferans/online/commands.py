"""Strict command decoding and domain transitions; no external effects."""

from __future__ import annotations

from collections.abc import Mapping

from preferans.domain.auction import AuctionAction, Bid, BidKind, RuleViolation
from preferans.domain.cards import Card, Rank, Suit
from preferans.domain.claims import offer_claim, vote_claim
from preferans.domain.game import (
    DefenseDecision,
    DefenseMode,
    GameState,
    auction_action,
    choose_defense_mode,
    concede_without_three,
    decide_defense,
    declare_contract,
    discard_cards,
    offer_misere,
    play_card,
    vote_misere,
)


def _keys(data: Mapping, expected: set[str]) -> None:
    if set(data) != expected:
        raise RuleViolation("Command arguments must match the exact schema")


def _seat(value: object) -> int:
    if type(value) is not int or value not in range(3):
        raise RuleViolation("Seat must be 0, 1 or 2")
    return value


def _card(value: object) -> Card:
    if not isinstance(value, dict):
        raise RuleViolation("Card must be an object")
    _keys(value, {"suit", "rank"})
    try:
        return Card(Suit(value["suit"]), Rank(value["rank"]))
    except (ValueError, TypeError) as exc:
        raise RuleViolation("Unknown card") from exc


def _bid(value: object) -> Bid:
    if not isinstance(value, dict):
        raise RuleViolation("Bid must be an object")
    _keys(value, {"kind", "level", "suit"})
    try:
        kind = BidKind(value["kind"])
        suit = None if value["suit"] is None else Suit(value["suit"])
        return Bid(kind, value["level"], suit)
    except (ValueError, TypeError) as exc:
        raise RuleViolation("Unknown bid") from exc


def apply_command(state: GameState, seat: int, action: str, data: object) -> GameState:
    """Actor is the authenticated seat, never a client-chosen UID."""
    _seat(seat)
    if not isinstance(data, dict) or len(data) > 8:
        raise RuleViolation("Invalid command arguments")
    if state.claim_pending and action != "claim_vote":
        raise RuleViolation("Resolve the remaining-tricks offer first")
    if action == "claim_offer":
        _keys(data, set())
        return offer_claim(state, seat)
    if action == "claim_vote":
        _keys(data, {"approve"})
        return vote_claim(state, seat, data["approve"])
    if action == "bid":
        _keys(data, {"bid"})
        return auction_action(state, seat, AuctionAction.place(_bid(data["bid"])))
    if action in {"pass", "here"}:
        _keys(data, set())
        operation = AuctionAction.pass_turn() if action == "pass" else AuctionAction.here()
        return auction_action(state, seat, operation)
    if action == "discard":
        _keys(data, {"cards"})
        values = data["cards"]
        if not isinstance(values, list) or len(values) != 2:
            raise RuleViolation("Discard requires two cards")
        return discard_cards(state, seat, (_card(values[0]), _card(values[1])))
    if action == "declare":
        _keys(data, {"bid"})
        return declare_contract(state, seat, _bid(data["bid"]))
    if action == "misere_offer":
        _keys(data, set())
        return offer_misere(state, seat)
    if action == "misere_vote":
        _keys(data, {"approve"})
        return vote_misere(state, seat, data["approve"])
    if action == "defense":
        _keys(data, {"decision"})
        try:
            choice = DefenseDecision(data["decision"])
        except ValueError as exc:
            raise RuleViolation("Invalid defense decision") from exc
        return decide_defense(state, seat, choice)
    if action == "mode":
        _keys(data, {"mode"})
        try:
            choice = DefenseMode(data["mode"])
        except ValueError as exc:
            raise RuleViolation("Invalid defense mode") from exc
        return choose_defense_mode(state, seat, choice)
    if action == "play":
        _keys(data, {"card", "owner"})
        return play_card(state, seat, _card(data["card"]), owner=_seat(data["owner"]))
    if action == "without_three":
        _keys(data, {"bid"})
        return concede_without_three(state, seat, _bid(data["bid"]))
    raise RuleViolation("Unsupported command")


def redacted_action(action: str, args: dict) -> dict:
    """Public event body excludes discarded and privately played content."""
    if action in {"bid", "declare", "without_three"}:
        return {"bid": args["bid"]}
    if action in {"play"}:
        return {"owner": args["owner"], "card": args["card"]}
    if action in {"defense", "mode", "misere_vote", "claim_vote"}:
        return {k: args[k] for k in args}
    return {}
