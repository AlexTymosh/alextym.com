"""Explicit self-report of an exposed card and unanimous resolution."""

from __future__ import annotations

from dataclasses import replace

from preferans.domain.game import GameState, Phase
from preferans.domain.ledger import EntryKind, LedgerEntry, ScoreState
from preferans.online.commands import _card
from preferans.online.controls import ControlError, timer_cost
from preferans.online.pause_clock import reasons, transition

ACTIONS = frozenset({"reveal_report", "reveal_propose", "reveal_vote"})
REASON = "accidental_reveal"


def change(
    control: dict,
    room: dict,
    game: GameState,
    score: ScoreState,
    seat: int,
    action: str,
    args: dict,
    now: int,
) -> tuple[dict, ScoreState, bool]:
    if type(seat) is not int or seat not in range(3):
        raise ControlError(403, "Seat required")
    if (
        room["status"] != "playing"
        or not isinstance(game, GameState)
        or game.phase == Phase.FINISHED
    ):
        raise ControlError(409, "No active deal")
    incident = control.get("reveal")
    if action == "reveal_report":
        if set(args) != {"card"}:
            raise ControlError(422, "A revealed card is required")
        if incident or control.get("vote") or reasons(control) - {"connection_lost"}:
            raise ControlError(409, "Resolve the current decision first")
        try:
            card = _card(args["card"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ControlError(422, "Invalid card") from exc
        if (
            card not in game.hands[seat]
            or seat in game.exposed_hands
            or card in game.widow[: game.widow_revealed]
        ):
            raise ControlError(422, "Report only a hidden card from your own hand")
        public = {"suit": card.suit.value, "rank": card.rank.value}
        prior = control.get("revealed_cards", [])
        if any(item["seat"] == seat and item["card"] == public for item in prior):
            raise ControlError(409, "This card has already been reported")
        incident = {
            "id": room["version"] + 1,
            "game_id": room["game_id"],
            "seat": seat,
            "card": public,
            "proposal": None,
        }
        control["reveal"] = incident
        control["revealed_cards"] = [*prior, {"seat": seat, "card": public}]
        control["candidate"] = None  # No undo across newly disclosed information.
        transition(control, reasons(control) | {REASON}, now)
        return dict(incident), score, False
    if not incident or incident["game_id"] != room["game_id"]:
        raise ControlError(409, "No matching disclosure")
    if "connection_lost" in reasons(control):
        raise ControlError(409, "Wait for the other players")
    if type(args.get("id")) is not int or args["id"] != incident["id"]:
        raise ControlError(409, "Disclosure changed")
    if action == "reveal_propose":
        if set(args) != {"id", "decision", "amount"} or incident["proposal"] is not None:
            raise ControlError(422, "Invalid or duplicate proposal")
        decision, amount = args["decision"], args["amount"]
        if decision not in ("continue", "redeal", "penalty"):
            raise ControlError(422, "Invalid resolution")
        if decision == "penalty":
            if game.is_passout or game.contract is not None:
                if amount is not None:
                    raise ControlError(422, "Penalty is calculated by the server")
                amount = 3 * timer_cost(game, score)
            elif type(amount) is not int or not 1 <= amount <= 1000:
                raise ControlError(422, "Agree an integer penalty before the contract")
        elif amount is not None:
            raise ControlError(422, "Unexpected penalty amount")
        votes = [False, False, False]
        votes[seat] = True
        proposal = {
            "id": room["version"] + 1,
            "decision": decision,
            "amount": amount,
            "votes": votes,
        }
        incident["proposal"] = proposal
        return {"incident_id": incident["id"], **proposal}, score, False
    if action != "reveal_vote" or set(args) != {"id", "proposal_id", "approve"}:
        raise ControlError(422, "Invalid disclosure vote")
    proposal = incident["proposal"]
    if (
        not proposal
        or type(args["proposal_id"]) is not int
        or args["proposal_id"] != proposal["id"]
    ):
        raise ControlError(409, "Proposal changed")
    if type(args["approve"]) is not bool:
        raise ControlError(422, "Invalid vote")
    if proposal["votes"][seat]:
        raise ControlError(409, "Vote already recorded")
    event = {
        "incident_id": incident["id"],
        "proposal_id": proposal["id"],
        "decision": proposal["decision"],
        "amount": proposal["amount"],
        "approve": args["approve"],
    }
    if not args["approve"]:
        incident["proposal"] = None
        return {**event, "outcome": "refused"}, score, False
    proposal["votes"][seat] = True
    if not all(proposal["votes"]):
        return {**event, "outcome": "pending"}, score, False
    if proposal["decision"] == "penalty":
        target, amount = incident["seat"], proposal["amount"]
        hill = list(score.hill)
        hill[target] += amount
        entry = LedgerEntry(
            len(score.entries) + 1, room["game_id"], EntryKind.HILL, target, amount, REASON
        )
        score = replace(score, hill=tuple(hill), entries=(*score.entries, entry))
    control.pop("reveal")
    transition(control, reasons(control) - {REASON}, now)
    return (
        {**event, "outcome": "accepted", "target": incident["seat"], "game_id": room["game_id"]},
        score,
        proposal["decision"] == "redeal",
    )
