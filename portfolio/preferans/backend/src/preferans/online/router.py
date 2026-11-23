"""Protected API surface. The website mounts this router under host auth."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .store import FirestoreRooms, StoreError

router = APIRouter(prefix="/preferans", tags=["Preferans"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Create(Strict):
    idempotency_key: str = Field(min_length=8, max_length=128)


class Mutation(Create):
    expected_version: int = Field(ge=0)


class Command(Mutation):
    action: Literal[
        "bid",
        "pass",
        "here",
        "discard",
        "declare",
        "defense",
        "mode",
        "play",
        "without_three",
        "pulse",
        "counter_start",
        "undo_request",
        "undo_vote",
        "preset",
    ]
    args: dict[str, Any] = Field(default_factory=dict)


class Adjust(Mutation):
    field: Literal["hill", "pool", "vist"]
    seat: int = Field(ge=0, le=2)
    against: int | None = Field(default=None, ge=0, le=2)
    delta: int = Field(ge=-1000, le=1000)
    reason: str = Field(min_length=5, max_length=180)


class Settle(Mutation):
    regular_route: Literal["pool", "hill_first"] = "pool"
    passout_routes: tuple[
        Literal["pool", "hill_first", "help"],
        Literal["pool", "hill_first", "help"],
        Literal["pool", "hill_first", "help"],
    ] = ("pool", "pool", "pool")


def _context(request: Request) -> tuple[FirestoreRooms, str, bool]:
    # The host guard sets these only after signed Firebase verification + grant.
    uid = getattr(request.state, "preferans_uid", None)
    owner = getattr(request.state, "preferans_owner", False)
    if not isinstance(uid, str) or not uid or type(owner) is not bool:
        raise HTTPException(403, "Access denied")
    try:
        from firebase_admin import firestore, get_app

        db = firestore.client(app=get_app("portfolio-lab"))
    except Exception as exc:
        raise HTTPException(503, "Storage unavailable") from exc
    return FirestoreRooms(db), uid, owner


def _execute(request: Request, method: str, *args: Any, **kwargs: Any) -> dict:
    store, uid, owner = _context(request)
    try:
        call = getattr(store, method)
        if method in {"start", "settle", "view", "events", "admin_adjust"}:
            kwargs["owner"] = owner
        return call(*args, uid=uid, **kwargs)
    except StoreError as exc:
        raise HTTPException(exc.code, exc.detail) from exc
    except Exception as exc:
        # Do not return Google SDK errors or internal state in an HTTP response.
        raise HTTPException(503, "Storage unavailable") from exc


@router.post("/rooms", status_code=201)
def create_room(request: Request, body: Create) -> dict:
    return _execute(request, "create", token=body.idempotency_key)


@router.post("/rooms/{room_id}/join")
def join_room(room_id: str, request: Request, body: Mutation) -> dict:
    return _execute(
        request, "join", room_id, token=body.idempotency_key, expected_version=body.expected_version
    )


@router.post("/rooms/{room_id}/start")
def start_room(room_id: str, request: Request, body: Mutation) -> dict:
    return _execute(
        request,
        "start",
        room_id,
        token=body.idempotency_key,
        expected_version=body.expected_version,
    )


@router.post("/rooms/{room_id}/commands")
def game_command(room_id: str, request: Request, body: Command) -> dict:
    return _execute(
        request,
        "command",
        room_id,
        token=body.idempotency_key,
        expected_version=body.expected_version,
        action=body.action,
        args=body.args,
    )


@router.post("/rooms/{room_id}/settle")
def settle_room(room_id: str, request: Request, body: Settle) -> dict:
    return _execute(
        request,
        "settle",
        room_id,
        token=body.idempotency_key,
        expected_version=body.expected_version,
        args={
            "regular_route": body.regular_route,
            "passout_routes": list(body.passout_routes),
        },
    )


@router.get("/rooms/{room_id}/view")
def room_view(room_id: str, request: Request, since_version: int | None = None) -> dict:
    return _execute(request, "view", room_id, since_version=since_version)


@router.get("/rooms/{room_id}/events")
def room_events(room_id: str, request: Request, limit: int = 30) -> dict:
    return _execute(request, "events", room_id, limit=limit)


@router.get("/rooms/{room_id}/invitation")
def room_invitation(room_id: str, request: Request) -> dict:
    """Only admitted Test/Admin users may view a room's public lobby envelope."""
    if getattr(request.state, "portfolio_lab_role", None) not in {"Test", "Admin"}:
        raise HTTPException(403, "Game participation requires Test or Admin access")
    return _execute(request, "invitation", room_id)


@router.post("/rooms/{room_id}/adjust")
def room_adjust(room_id: str, request: Request, body: Adjust) -> dict:
    return _execute(
        request,
        "admin_adjust",
        room_id,
        token=body.idempotency_key,
        expected_version=body.expected_version,
        args={
            "field": body.field,
            "seat": body.seat,
            "against": body.against,
            "delta": body.delta,
            "reason": body.reason,
        },
    )
