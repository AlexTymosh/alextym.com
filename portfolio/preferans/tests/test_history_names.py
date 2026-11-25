"""Display names are attached only to existing opaque ranking identities."""

from preferans.domain.history import public_player_id
from preferans.online.history_names import ranking_names
from test_secure_rooms import FakeDB


def test_history_names_only_match_ranked_players():
    db = FakeDB()
    db.docs["portfolio_lab_profiles/uid-a"] = {
        "first_name": "Alice",
        "last_name": "Example",
        "email": "private@example.com",
        "avatar_data_url": "private",
    }
    db.docs["portfolio_lab_profiles/uid-b"] = {"first_name": "unranked"}
    db.docs["portfolio_lab_profiles/uid-c"] = {"first_name": "bad@example.com"}
    result = ranking_names(db, {public_player_id("uid-a"), public_player_id("uid-c")})
    assert result == {public_player_id("uid-a"): "Alice Example"}
    assert "uid-a" not in str(result)
    assert "unranked" not in str(result)
    assert ranking_names(db, set()) == {}
