"""Ephemeral, seat-scoped defense cues over the authenticated realtime hub.

Called under the hub lock. Only already-authorized card projections are used;
no hidden cards, database reads/writes, game actions, or event ledger entries.
"""


def _seat(value):
    return type(value) is int and value in range(3)


def _card(value):
    return (
        isinstance(value, dict)
        and set(value) == {"suit", "rank"}
        and value["suit"] in ("S", "C", "D", "H")
        and type(value["rank"]) is int
        and 7 <= value["rank"] <= 14
    )


def _defender(view):
    if (
        not view
        or view.get("status") != "playing"
        or view.get("phase") not in ("play", "opening_lead")
    ):
        return False
    seat, declarer = view.get("my_seat"), view.get("declarer")
    if not _seat(seat) or not _seat(declarer) or seat == declarer or view.get("is_passout"):
        return False
    controls = view.get("controls") or {}
    if (
        controls.get("paused")
        or controls.get("undo")
        or (view.get("claim") or {}).get("status") == "pending"
    ):
        return False
    kind = (view.get("contract") or {}).get("kind")
    return kind in ("misere", "misere_no_widow") or (
        kind in ("regular", "ten_no_widow") and "vist" in (view.get("defense") or [])
    )


def _visible(view, owner, card):
    if owner == view.get("my_seat"):
        return card in (view.get("hand") or [])
    return any(
        owner == hand.get("seat") and card in hand.get("cards", [])
        for hand in view.get("open_hands", [])
    )


def _scope(view):
    game, version = view.get("game_id"), view.get("version")
    if isinstance(game, str) and type(version) is int:
        return game, version
    return None


def _sync_scope(room, scope):
    if room.defense_hint_scope != scope:
        room.defense_hints.clear()
        room.defense_hint_scope = scope


def receive_hint(room, uid, frame):
    """Validate against both current private projections; reject silently."""
    if not isinstance(frame, dict) or set(frame) != {
        "type",
        "protocol",
        "game_id",
        "version",
        "owner",
        "card",
        "raised",
    }:
        return False
    if (
        frame["type"] != "defense_hint"
        or type(frame["protocol"]) is not int
        or frame["protocol"] != 1
    ):
        return False
    actor = room.views.get(uid)
    if not _defender(actor):
        return False
    scope = _scope(actor)
    if scope is None or scope != (frame["game_id"], frame["version"]) or scope[1] != room.revision:
        return False
    if type(frame["version"]) is not int or type(frame["raised"]) is not bool:
        return False
    owner, card = frame["owner"], frame["card"]
    declarer = actor["declarer"]
    if not _seat(owner) or owner == declarer or not _card(card):
        return False
    other = 3 - actor["my_seat"] - declarer
    peer = next((v for v in room.views.values() if v.get("my_seat") == other), None)
    if not _defender(peer) or _scope(peer) != scope or peer.get("declarer") != declarer:
        return False
    if not _visible(actor, owner, card) or not _visible(peer, owner, card):
        return False
    _sync_scope(room, scope)
    key = (owner, card["suit"], card["rank"])
    if frame["raised"]:
        room.defense_hints[key] = {"owner": owner, "card": dict(card)}
    else:
        room.defense_hints.pop(key, None)
    return True


def decorated_view(room, view):
    """Do not mutate the cached projection. No cue data for declarers/observers."""
    if not _defender(view) or _scope(view) is None or view["version"] != room.revision:
        return view
    _sync_scope(room, _scope(view))
    return {
        **view,
        "defense_hints": [
            mark
            for _, mark in sorted(room.defense_hints.items())
            if mark["owner"] != view["declarer"] and _visible(view, mark["owner"], mark["card"])
        ],
    }
