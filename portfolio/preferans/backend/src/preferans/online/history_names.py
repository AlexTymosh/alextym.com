"""Bounded name-only lookup for project-authorized historical statistics."""

from preferans.domain.history import public_player_id


def ranking_names(db, player_ids: set[str]) -> dict[str, str]:
    if not player_ids:
        return {}
    # Local import avoids coupling the room store and lobby at import time.
    from preferans.online.lobby import profile_projection

    names = {}
    # Read only the two display-name fields. Never project account identifiers,
    # photos, emails or profiles that do not belong to the returned ranking.
    query = db.collection("portfolio_lab_profiles").select(["first_name", "last_name"]).limit(1001)
    for snapshot in query.stream(timeout=5.0):
        player_id = public_player_id(snapshot.id)
        if player_id in player_ids:
            name = profile_projection(snapshot.to_dict())["name"]
            if name:
                names[player_id] = name
            if len(names) == len(player_ids):
                break
    return names
