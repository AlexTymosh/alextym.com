"""Explicit allow-listed serialization for *server-only* domain state.

Never expose the result of ``encode`` to a browser. It includes secret hands.
Avoid pickle, eval, dynamic imports, object-path lookup and JSON object hooks.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum

from preferans.domain import auction, cards, game, ledger, play, rulesets, scoring

_ALLOWED = {}
for module in (auction, cards, game, ledger, play, rulesets, scoring):
    for name in dir(module):
        candidate = getattr(module, name)
        if isinstance(candidate, type) and candidate.__module__ == module.__name__:
            if is_dataclass(candidate) or (issubclass(candidate, Enum)):
                _ALLOWED[name] = candidate


def encode(obj: object, depth: int = 0) -> object:
    """Map dataclasses, enums, tuples and sets into Firestore-safe primitives."""
    if depth > 60:
        raise ValueError("State nesting too deep")
    if isinstance(obj, Enum):
        if type(obj).__name__ not in _ALLOWED:
            raise ValueError("Unknown enum")
        return {"$enum": type(obj).__name__, "value": obj.value}
    if is_dataclass(obj) and not isinstance(obj, type):
        if type(obj).__name__ not in _ALLOWED:
            raise ValueError("Unknown state class")
        return {
            "$type": type(obj).__name__,
            "fields": {f.name: encode(getattr(obj, f.name), depth + 1) for f in fields(obj)},
        }
    if isinstance(obj, tuple):
        return {"$tuple": [encode(x, depth + 1) for x in obj]}
    if isinstance(obj, frozenset):
        return {"$set": [encode(x, depth + 1) for x in sorted(obj, key=str)]}
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    raise ValueError("Unsupported state value")


def decode(obj: object, depth: int = 0) -> object:
    """Decode only known domain types; corrupted Firestore state fails closed."""
    if depth > 60:
        raise ValueError("State nesting too deep")
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    if not isinstance(obj, dict) or not all(isinstance(k, str) for k in obj):
        raise ValueError("Invalid state encoding")
    if set(obj) == {"$tuple"} and isinstance(obj["$tuple"], list):
        return tuple(decode(v, depth + 1) for v in obj["$tuple"])
    if set(obj) == {"$set"} and isinstance(obj["$set"], list):
        return frozenset(decode(v, depth + 1) for v in obj["$set"])
    if set(obj) == {"$enum", "value"}:
        cls = _ALLOWED.get(obj["$enum"])
        if cls is None or not issubclass(cls, Enum):
            raise ValueError("Unknown state enum")
        return cls(obj["value"])
    if set(obj) == {"$type", "fields"}:
        cls = _ALLOWED.get(obj["$type"])
        kwargs = obj["fields"]
        if cls is None or not is_dataclass(cls) or not isinstance(kwargs, dict):
            raise ValueError("Unknown state object")
        expected = {f.name for f in fields(cls)}
        # Explicit additive migrations only. Unknown fields still fail closed.
        if cls is game.GameState:
            kwargs = dict(kwargs)
            kwargs.setdefault("misere_votes", {"$set": []})
            kwargs.setdefault("misere_resume_turn", None)
            kwargs.setdefault("misere_refused_at", None)
            kwargs.setdefault("claim", None)
        if cls is game.TrickClaim:
            kwargs = dict(kwargs)
            kwargs.setdefault("display_order", {"$tuple": []})
            kwargs.setdefault("defender_target", None)
        if set(kwargs) != expected:
            raise ValueError("State schema mismatch")
        return cls(**{name: decode(val, depth + 1) for name, val in kwargs.items()})
    raise ValueError("Unknown state tag")
