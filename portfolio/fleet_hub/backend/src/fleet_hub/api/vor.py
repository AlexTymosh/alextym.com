"""Protected API for a stand-alone synthetic fleet demo. Mounted at /api/vor."""

from __future__ import annotations

import os
import secrets
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from fleet_hub.api.dependencies import (
    COOKIE,
    SESSION_TTL,
    enabled,
    required,
    same_origin,
    secret as secret,
    session_valid,
    sign,
)
from fleet_hub.services import message_delivery, vor_store
from fleet_hub.services.message_delivery import valid_email
from fleet_hub.services.vor_exports import build_xlsx, build_ics

router = APIRouter(prefix="/vor", tags=["Fleet VOR demo"])
_login_attempts: dict[str, list[float]] = {}


class Login(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class NewMessage(BaseModel):
    vehicle_id: int
    ticket_id: str | None = Field(default=None, max_length=64)
    kind: Literal["internal", "email"]
    text: str = Field(min_length=1, max_length=2500)
    subject: str | None = Field(default=None, max_length=200)
    request_id: str | None = Field(
        default=None, min_length=32, max_length=64, pattern=r"^[a-f0-9-]+$"
    )


class NewBooking(BaseModel):
    vehicle_id: int
    kind: Literal["MOT", "Inspection", "Service"]
    booked_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    garage: str = Field(min_length=1, max_length=100)


class NextStep(BaseModel):
    vehicle_id: int
    ticket_id: str


class ChangeScenario(BaseModel):
    vehicle_id: int
    ticket_id: str = Field(min_length=1, max_length=64)
    scenario: str = Field(min_length=1, max_length=40)


class ChangeResponsible(BaseModel):
    vehicle_id: int
    name: Literal["Alex Tym", "Victoria B.", "Jason W.", "Janine M.", "Gosha T."]


class ChangeWorkshop(BaseModel):
    vehicle_id: int
    garage: str = Field(min_length=1, max_length=100)


class NewContact(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    role: Literal["internal", "external"]


class UpdateContact(NewContact):
    pass


class Subscribe(BaseModel):
    vehicle_id: int
    contact_id: int
    subscribed: bool


@router.get("/session")
def session(request: Request) -> dict:
    return {
        "enabled": enabled(),
        "authenticated": enabled() and session_valid(request),
        "liveEmail": os.getenv("VOR_DEMO_SEND_REAL_EMAIL", "false").lower() == "true",
    }


@router.post("/login")
def login(body: Login, request: Request, response: Response) -> dict:
    same_origin(request)
    if not enabled():
        raise HTTPException(404, "Demo disabled")
    configured = os.getenv("VOR_DEMO_PASSWORD", "")
    if not configured:
        raise HTTPException(503, "VOR_DEMO_PASSWORD must be configured")
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = [x for x in _login_attempts.get(key, []) if now - x < 60]
    if len(attempts) >= 8:
        raise HTTPException(429, "Too many attempts. Retry in one minute.")
    if not secrets.compare_digest(body.password, configured):
        attempts.append(now)
        _login_attempts[key] = attempts
        raise HTTPException(401, "Incorrect password")
    _login_attempts.pop(key, None)
    stamp = str(int(time.time()))
    is_https = request.headers.get("x-forwarded-proto", request.url.scheme).lower() == "https"
    response.set_cookie(
        COOKIE,
        f"{stamp}.{sign(stamp)}",
        max_age=SESSION_TTL,
        httponly=True,
        secure=is_https,
        samesite="strict",
        path="/api/vor",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, request: Request) -> dict:
    same_origin(request)
    response.delete_cookie(COOKIE, path="/api/vor")
    return {"ok": True}


@router.get("/bootstrap", dependencies=[Depends(required)])
def bootstrap() -> dict:
    return vor_store.snapshot()


@router.get("/export.xlsx", dependencies=[Depends(required)])
def export_excel() -> Response:
    return Response(
        content=build_xlsx(vor_store.snapshot()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="fleet-vor-demo.xlsx"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/calendar.ics", dependencies=[Depends(required)])
def export_calendar() -> Response:
    return Response(
        content=build_ics(vor_store.snapshot()),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="fleet-vor-demo.ics"',
            "Cache-Control": "no-store",
        },
    )


_MESSAGE_HTTP_ERRORS: dict[str, tuple[int, str]] = {
    "invalid_record": (422, "Invalid fleet message"),
    "no_subscribers": (422, "This vehicle has no subscribers"),
    "invalid_subscriber_email": (422, "Subscriber directory contains invalid emails"),
    "policy_missing": (503, "Live sending requires an allowed email domain or recipient policy"),
    "recipient_not_allowed": (
        403,
        "A subscribed address is outside permitted recipient domains. Check Manage.",
    ),
    "mail_config_missing": (
        503,
        "Live email requires a verified sender, RESEND_API_KEY and HTTPS VOR_DEMO_PUBLIC_URL",
    ),
    "public_url_unreachable": (503, "Public URL must be reachable by recipients"),
    "daily_quota_exceeded": (429, "Daily recipient limit would be exceeded"),
    "provider_unavailable": (502, "Email provider unavailable"),
    "request_id_conflict": (422, "Request ID was reused for different email content"),
    "delivery_uncertain": (409, "Email already attempted; verify delivery before retrying"),
}


@router.post("/messages", dependencies=[Depends(required)])
def create_message(body: NewMessage, request: Request) -> dict:
    same_origin(request)
    try:
        return message_delivery.post_message(
            vehicle_id=body.vehicle_id,
            ticket_id=body.ticket_id,
            kind=body.kind,
            text=body.text,
            subject=body.subject,
            request_id=body.request_id,
        )
    except message_delivery.MessageDeliveryError as exc:
        code, default_detail = _MESSAGE_HTTP_ERRORS[exc.reason]
        raise HTTPException(code, exc.detail if exc.detail is not None else default_detail) from exc


@router.post("/bookings", dependencies=[Depends(required)])
def create_booking(body: NewBooking, request: Request) -> dict:
    same_origin(request)
    try:
        pk = vor_store.add_booking(body.vehicle_id, body.kind, body.booked_date, body.garage)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        # Unique booking constraint, not an opaque 500.
        import sqlite3

        if isinstance(exc, sqlite3.IntegrityError):
            raise HTTPException(409, "This booking already exists") from exc
        raise
    return {"id": pk}


@router.post("/advance", dependencies=[Depends(required)])
def advance(body: NextStep, request: Request) -> dict:
    same_origin(request)
    from fleet_hub.api.vor_checklist import AdvanceStage, advance_with_checks

    return advance_with_checks(
        AdvanceStage(vehicle_id=body.vehicle_id, ticket_id=body.ticket_id), request
    )


@router.post("/scenario", dependencies=[Depends(required)])
def change_scenario(body: ChangeScenario, request: Request) -> dict:
    same_origin(request)
    try:
        vor_store.change_workflow_scenario(body.vehicle_id, body.ticket_id, body.scenario)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True}


@router.post("/responsible", dependencies=[Depends(required)])
def set_responsible(body: ChangeResponsible, request: Request) -> dict:
    same_origin(request)
    try:
        vor_store.change_responsible(body.vehicle_id, body.name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True}


@router.post("/workshop", dependencies=[Depends(required)])
def set_workshop(body: ChangeWorkshop, request: Request) -> dict:
    same_origin(request)
    try:
        vor_store.change_workshop(body.vehicle_id, body.garage)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True}


@router.post("/contacts", dependencies=[Depends(required)])
def create_contact(body: NewContact, request: Request) -> dict:
    same_origin(request)
    if not valid_email(body.email):
        raise HTTPException(422, "Invalid email")
    return {"id": vor_store.add_contact(body.name, body.email, body.role)}


@router.post("/subscribers", dependencies=[Depends(required)])
def update_subscriber(body: Subscribe, request: Request) -> dict:
    same_origin(request)
    try:
        vor_store.toggle_subscriber(body.vehicle_id, body.contact_id, body.subscribed)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True}


@router.post("/contacts/{contact_id}/update", dependencies=[Depends(required)])
def edit_contact(contact_id: int, body: UpdateContact, request: Request) -> dict:
    same_origin(request)
    if not valid_email(body.email):
        raise HTTPException(422, "Invalid email")
    try:
        vor_store.update_contact(contact_id, body.name, body.email, body.role)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"ok": True}
