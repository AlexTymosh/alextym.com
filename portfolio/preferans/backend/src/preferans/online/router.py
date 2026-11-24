"""Protected API surface. The website mounts this router under host auth."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .store import FirestoreRooms, StoreError
from .media import MediaRooms
from .lobby import can_create_room, directory, room_profiles
from .realtime import (
    PROTOCOL,
    TICKET_MS,
    HubError,
    enabled as realtime_enabled,
    hub,
    now_ms,
    origin_allowed,
)

router = APIRouter(prefix="/preferans", tags=["Preferans"])
logger = logging.getLogger(__name__)


def _storage_failure(request: Request, operation: str, stage: str, exc: Exception) -> None:
    # Log only an allowlisted envelope, never str(exc), traceback, request data,
    # Firebase identity/credentials, game state or provider error metadata.
    diagnostic = {
        "event": "preferans.storage.failed",
        "operation": operation,
        "stage": stage,
        "error_type": type(exc).__name__,
        "request_id": getattr(request.state, "request_id", None),
    }
    if exc.__cause__ is not None:
        diagnostic["cause_type"] = type(exc.__cause__).__name__
    logger.error(json.dumps(diagnostic, sort_keys=True))


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
        "lobby_ready",
        "lobby_config",
        "overlay_open",
        "overlay_close",
        "break_start",
        "break_ready",
        "music",
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


def _context(request: Request, operation: str) -> tuple[FirestoreRooms, str, bool]:
    # The host guard sets these only after signed Firebase verification + grant.
    uid = getattr(request.state, "preferans_uid", None)
    owner = getattr(request.state, "preferans_owner", False)
    if not isinstance(uid, str) or not uid or type(owner) is not bool:
        raise HTTPException(403, "Access denied")
    try:
        from firebase_admin import firestore, get_app

        db = firestore.client(app=get_app("portfolio-lab"))
        store = FirestoreRooms(db)
    except Exception as exc:
        _storage_failure(request, operation, "initialization", exc)
        raise HTTPException(503, "Storage unavailable") from exc
    return store, uid, owner


def _execute(request: Request, method: str, *args: Any, **kwargs: Any) -> dict:
    store, uid, owner = _context(request, method)
    try:
        call = getattr(store, method)
        if method in {"start", "settle", "view", "events", "admin_adjust"}:
            kwargs["owner"] = owner
        return call(*args, uid=uid, **kwargs)
    except StoreError as exc:
        if exc.code == 503:
            _storage_failure(request, method, "state", exc)
        raise HTTPException(exc.code, exc.detail) from exc
    except Exception as exc:
        # Do not return Google SDK errors or internal state in an HTTP response.
        _storage_failure(request, method, "operation", exc)
        raise HTTPException(503, "Storage unavailable") from exc


@router.post("/rooms", status_code=201)
def create_room(request: Request, body: Create) -> dict:
    if not can_create_room(
        getattr(request.state, "portfolio_lab_role", None),
        getattr(request.state, "preferans_owner", False),
    ):
        raise HTTPException(403, "Room creation requires project Admin")
    return _execute(request, "create", token=body.idempotency_key, require_ready=True)


@router.get("/rooms")
def list_rooms(request: Request) -> dict:
    role = getattr(request.state, "portfolio_lab_role", None)
    owner = getattr(request.state, "preferans_owner", False)
    if role not in {"Test", "Admin"} and not owner:
        raise HTTPException(403, "Game participation required")
    store, uid, _ = _context(request, "directory")
    try:
        return directory(store.db, uid, admin=can_create_room(role, owner))
    except StoreError as exc:
        raise HTTPException(exc.code, exc.detail) from exc
    except Exception as exc:
        _storage_failure(request, "directory", "operation", exc)
        raise HTTPException(503, "Storage unavailable") from exc


@router.get("/rooms/{room_id}/profiles")
def profiles(room_id: str, request: Request) -> dict:
    role = getattr(request.state, "portfolio_lab_role", None)
    if role not in {"Test", "Admin"} and not getattr(request.state, "preferans_owner", False):
        raise HTTPException(403, "Game participation required")
    store, uid, _ = _context(request, "profiles")
    try:
        return room_profiles(store.db, room_id, uid)
    except StoreError as exc:
        raise HTTPException(exc.code, exc.detail) from exc
    except Exception as exc:
        _storage_failure(request, "profiles", "operation", exc)
        raise HTTPException(503, "Storage unavailable") from exc


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


@router.post("/rooms/{room_id}/realtime-ticket")
def realtime_ticket(room_id: str, request: Request, body: Strict) -> dict:
    if not realtime_enabled():
        raise HTTPException(404, "Not found")
    origin = request.headers.get("x-preferans-origin", "")
    if not origin_allowed(origin) or getattr(request.state, "portfolio_lab_role", None) not in {
        "Test",
        "Admin",
    }:
        raise HTTPException(403, "Realtime access denied")
    view = _execute(request, "view", room_id)
    seat = view.get("my_seat")
    if seat not in (0, 1, 2):
        raise HTTPException(403, "Seat required")
    try:
        token = hub.issue(
            room_id,
            request.state.preferans_uid,
            seat,
            origin,
            request.headers.get("authorization", ""),
            now_ms(),
        )
    except HubError as exc:
        raise HTTPException(503, "Realtime unavailable") from exc
    return {"ticket": token, "protocol": PROTOCOL, "expires_in_ms": TICKET_MS}


@router.get("/rooms/{room_id}/view")
def room_view(room_id: str, request: Request, since_version: int | None = None) -> dict:
    return _execute(request, "view", room_id, since_version=since_version)


@router.get("/rooms/{room_id}/events")
def room_events(room_id: str, request: Request, limit: int = 30) -> dict:
    return _execute(request, "events", room_id, limit=limit)


class MediaCommand(Create):
    action: Literal[
        "presence", "signal", "record_request", "record_vote", "record_start", "record_stop"
    ]
    args: dict[str, Any] = Field(default_factory=dict)


def _media(request: Request, room_id: str, uid_operation: str, **kwargs: Any) -> dict:
    # The new live-only mode and legacy consent/recording transport must never
    # operate simultaneously. Preserve old stored documents for audited cleanup.
    if (
        os.getenv("PREFERANS_MEDIA_ENABLED") != "true"
        or os.getenv("PREFERANS_LIVE_MEDIA_WS_ENABLED") == "true"
    ):
        raise HTTPException(404, "Not found")
    operation = f"media.{uid_operation}"
    base, uid, _ = _context(request, operation)
    try:
        service = MediaRooms(base.db, firestore_module=base.fs)
        return getattr(service, uid_operation)(room_id, uid, **kwargs)
    except StoreError as exc:
        if exc.code == 503:
            _storage_failure(request, operation, "state", exc)
        raise HTTPException(exc.code, exc.detail) from exc
    except Exception as exc:
        _storage_failure(request, operation, "operation", exc)
        raise HTTPException(503, "Media signalling unavailable") from exc


@router.get("/rooms/{room_id}/media")
def room_media(room_id: str, request: Request, cursor: int = 0) -> dict:
    return _media(request, room_id, "view", cursor=cursor)


@router.post("/rooms/{room_id}/media")
def room_media_command(room_id: str, request: Request, body: MediaCommand) -> dict:
    return _media(
        request,
        room_id,
        "command",
        token=body.idempotency_key,
        action=body.action,
        args=body.args,
    )


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


@router.get("/realtime-metrics")
def realtime_metrics(request: Request) -> dict:
    if not realtime_enabled():
        raise HTTPException(404, "Not found")
    if not getattr(request.state, "preferans_owner", False):
        raise HTTPException(403, "Owner required")
    with hub.lock:
        return {
            "scope": "process-local-estimates",
            "metrics": dict(hub.metrics),
            "active_rooms": len(hub.rooms),
        }


@router.get("/history")
def game_history(request: Request, limit: int = 50) -> dict:
    return _execute(request, "history", limit=limit)


@router.get("/rankings")
def game_rankings(request: Request) -> dict:
    return _execute(request, "rankings")


@router.get("/results/{room_id}")
def game_result(room_id: str, request: Request) -> dict:
    return _execute(request, "result", room_id)
