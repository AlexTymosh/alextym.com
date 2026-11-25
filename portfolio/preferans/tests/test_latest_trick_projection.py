from dataclasses import replace

from preferans.domain.cards import FULL_DECK, deal
from preferans.domain.game import Phase, start_game
from preferans.domain.play import CompletedTrick, PlayedCard
from preferans.online.views import seat_view


def test_only_globally_latest_trick_is_projected():
    game = start_game(deal(FULL_DECK, 2))
    first = tuple(PlayedCard(i, i, game.hands[i][0]) for i in range(3))
    second = tuple(PlayedCard(i, i, game.hands[i][1]) for i in range(3))
    game = replace(
        game,
        phase=Phase.FINISHED,
        completed_tricks=(
            CompletedTrick(1, first, 0, first[0].card.suit),
            CompletedTrick(2, second, 1, second[0].card.suit),
        ),
        tricks_won=(1, 1, 0),
    )
    room = {
        "id": "a" * 32,
        "status": "awaiting_settlement",
        "seats": ["a", "b", "c"],
        "admin_uid": "a",
        "game_id": "deal",
    }
    # No score avoids settlement-option computation on this synthetic partial deal.
    for uid in ("a", "b", "c"):
        view = seat_view(room, game, None, uid, 2)
        assert view["last_trick_winner"] == 1
        assert view["tricks_won"] == [1, 1, 0]
        assert "last_won_tricks" not in view
        assert view["last_trick"] == [
            {
                "owner": play.owner,
                "card": {"suit": play.card.suit.value, "rank": play.card.rank.value},
            }
            for play in second
        ]
