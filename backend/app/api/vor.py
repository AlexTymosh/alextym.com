"""Protected API for a stand-alone synthetic fleet demo. Mounted at /api/vor."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import datetime
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.services import vor_store
from app.services.vor_exports import build_xlsx, build_ics

router = APIRouter(prefix='/vor', tags=['Fleet VOR demo'])
COOKIE = 'vor_demo_session'
SESSION_TTL = 8 * 3600
_login_attempts: dict[str, list[float]] = {}


def enabled() -> bool:
    return os.getenv('VOR_DEMO_ENABLED','false').lower() == 'true'


def secret() -> bytes:
    return hashlib.sha256(('alextym-vor-demo:v1:' + os.getenv('VOR_DEMO_PASSWORD', '')).encode()).digest()


def sign(payload: str) -> str:
    return hmac.new(secret(), payload.encode(), hashlib.sha256).hexdigest()


def session_valid(request: Request) -> bool:
    cookie = request.cookies.get(COOKIE, '')
    try:
        started, signature = cookie.split('.', 1)
        ts = int(started)
        return (ts <= time.time() < ts+SESSION_TTL) and hmac.compare_digest(signature,sign(started))
    except (ValueError, TypeError):
        return False


def required(request: Request) -> None:
    if not enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND,'Demo disabled')
    if not session_valid(request):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,'Password required')


def same_origin(request: Request) -> None:
    origin = request.headers.get('origin', '')
    # Next rewrite forwards Host/Origin; ensure browser POSTs originate from the displayed site.
    if origin:
        from urllib.parse import urlsplit
        origin_host = urlsplit(origin).netloc.lower()
        forwarded_host = (request.headers.get('x-forwarded-host') or request.headers.get('host') or '').split(',')[0].strip().lower()
        if origin_host != forwarded_host:
            # In some reverse proxy setups Host is the private backend while the browser origin is the frontend.
            trusted = {value.strip().lower() for value in os.getenv('VOR_DEMO_ALLOWED_ORIGINS','http://localhost:3000,http://127.0.0.1:3000').split(',') if value.strip()}
            if origin.lower() not in trusted:
                raise HTTPException(403,'Invalid origin')


class Login(BaseModel):
    password: str = Field(min_length=1,max_length=128)

class NewMessage(BaseModel):
    vehicle_id: int
    ticket_id: str | None = Field(default=None,max_length=64)
    kind: Literal['internal','email']
    text: str = Field(min_length=1,max_length=2500)
    subject: str | None = Field(default=None,max_length=200)

class NewBooking(BaseModel):
    vehicle_id: int
    kind: Literal['MOT','Inspection','Service']
    booked_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    garage: str = Field(min_length=1,max_length=100)

class NextStep(BaseModel):
    vehicle_id: int
    ticket_id: str

class ChangeScenario(BaseModel):
    vehicle_id: int
    ticket_id: str = Field(min_length=1,max_length=64)
    scenario: str = Field(min_length=1,max_length=40)

class ChangeResponsible(BaseModel):
    vehicle_id: int
    name: Literal['Alex Tym','Victoria B.','Jason W.','Janine M.','Gosha T.']

class ChangeWorkshop(BaseModel):
    vehicle_id: int
    garage: str = Field(min_length=1,max_length=100)

class NewContact(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    email: str = Field(min_length=3,max_length=254)
    role: Literal['internal','external']

class UpdateContact(NewContact):
    pass

class Subscribe(BaseModel):
    vehicle_id: int
    contact_id: int
    subscribed: bool


@router.get('/session')
def session(request: Request) -> dict:
    return {'enabled':enabled(), 'authenticated':enabled() and session_valid(request), 'liveEmail': os.getenv('VOR_DEMO_SEND_REAL_EMAIL','false').lower() == 'true'}


@router.post('/login')
def login(body: Login, request: Request, response: Response) -> dict:
    same_origin(request)
    if not enabled():
        raise HTTPException(404,'Demo disabled')
    configured = os.getenv('VOR_DEMO_PASSWORD','')
    if not configured:
        raise HTTPException(503,'VOR_DEMO_PASSWORD must be configured')
    key = request.client.host if request.client else 'unknown'
    now = time.monotonic()
    attempts = [x for x in _login_attempts.get(key,[]) if now-x<60]
    if len(attempts) >= 8:
        raise HTTPException(429,'Too many attempts. Retry in one minute.')
    if not secrets.compare_digest(body.password,configured):
        attempts.append(now)
        _login_attempts[key] = attempts
        raise HTTPException(401,'Incorrect password')
    _login_attempts.pop(key,None)
    stamp=str(int(time.time()))
    is_https = request.headers.get('x-forwarded-proto',request.url.scheme).lower() == 'https'
    response.set_cookie(COOKIE,f'{stamp}.{sign(stamp)}',max_age=SESSION_TTL,httponly=True,secure=is_https,samesite='strict',path='/api/vor')
    return {'ok':True}


@router.post('/logout')
def logout(response: Response, request: Request) -> dict:
    same_origin(request)
    response.delete_cookie(COOKIE,path='/api/vor')
    return {'ok':True}


@router.get('/bootstrap', dependencies=[Depends(required)])
def bootstrap() -> dict:
    return vor_store.snapshot()


@router.get('/export.xlsx', dependencies=[Depends(required)])
def export_excel() -> Response:
    return Response(content=build_xlsx(vor_store.snapshot()),
                    media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition':'attachment; filename="fleet-vor-demo.xlsx"',
                             'Cache-Control':'no-store'})


@router.get('/calendar.ics', dependencies=[Depends(required)])
def export_calendar() -> Response:
    return Response(content=build_ics(vor_store.snapshot()),
                    media_type='text/calendar; charset=utf-8',
                    headers={'Content-Disposition':'attachment; filename="fleet-vor-demo.ics"',
                             'Cache-Control':'no-store'})


EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


@router.post('/messages', dependencies=[Depends(required)])
def create_message(body: NewMessage, request: Request) -> dict:
    same_origin(request)
    recipients: list[str] = []
    direction = None
    try:
        registration = vor_store.validate_vehicle_ticket(body.vehicle_id, body.ticket_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    subject = body.subject
    if body.kind == 'email':
        recipients = vor_store.subscriber_emails(body.vehicle_id)
        if not recipients:
            raise HTTPException(422,'This vehicle has no subscribers')
        if any(not EMAIL_RE.fullmatch(email) for email in recipients):
            raise HTTPException(422,'Subscriber directory contains invalid emails')
        prefix = f'[{registration}]' + (f'[{body.ticket_id}]' if body.ticket_id else '')
        subject = f'{prefix} {body.subject or "Fleet update"}'
        real = os.getenv('VOR_DEMO_SEND_REAL_EMAIL','false').lower() == 'true'
        if real:
            # Recipients are always server-derived from the Manage directory, never from the POST body.
            # One-off exact addresses and entire trusted domains are supported.
            allowed = {x.strip().lower() for x in os.getenv('VOR_DEMO_ALLOWED_RECIPIENTS','').split(',') if x.strip()}
            domains = {x.strip().lower().lstrip('@') for x in os.getenv('VOR_DEMO_ALLOWED_EMAIL_DOMAINS','').split(',') if x.strip()}
            if not allowed and not domains:
                raise HTTPException(503, 'Live sending requires an allowed email domain or recipient policy')
            # Explicit '*' permits any domain, but addresses must still belong to
            # subscribed contacts and pass email validation and the daily quota.
            any_domain = '*' in domains
            unapproved = [
                email for email in recipients
                if not (any_domain or email in allowed or email.rsplit('@', 1)[-1] in domains)
            ]
            if unapproved:
                raise HTTPException(403, 'A subscribed address is outside permitted recipient domains. Check Manage.')
            limit = max(1,min(int(os.getenv('VOR_DEMO_EMAIL_LIMIT','15')),30))
            token = os.getenv('RESEND_API_KEY','')
            from_email = os.getenv('VOR_DEMO_FROM_EMAIL','') or os.getenv('CONTACT_FROM_EMAIL','')
            public_url=os.getenv('VOR_DEMO_PUBLIC_URL','').strip()
            if not token or not from_email or not public_url.startswith('https://'):
                raise HTTPException(503,'Live email requires a verified sender, RESEND_API_KEY and HTTPS VOR_DEMO_PUBLIC_URL')
            from urllib.parse import urlsplit
            host=urlsplit(public_url).hostname or ''
            if host in {'localhost','127.0.0.1'}:
                raise HTTPException(503,'Public URL must be reachable by recipients')
            # Mail message is a notification, not a copy of internal chatter.
            notification=(
                'This is a test demonstration of the Fleet VOR management system.\n\n'
                f'A new update has been posted for vehicle {registration}'
                + (f' (ticket {body.ticket_id})' if body.ticket_id else '')
                + '.\n\nOpen Fleet VOR Hub to read the update:\n'
                + public_url + '\n\nThis is a demonstration notification; no operational action is required. '
                'Please do not reply to this email.'
            )
            # All recipients receive one delivery, with all but the first in blind copy.
            payload: dict = {'from':from_email,'to':[recipients[0]],'subject':subject,'text':notification}
            if len(recipients)>1:
                payload['bcc']=recipients[1:]
            try:
                reservation_id = vor_store.reserve_email_delivery(len(recipients), limit)
            except ValueError:
                raise HTTPException(429,'Daily recipient limit would be exceeded') from None
            try:
                result = httpx.post('https://api.resend.com/emails',
                    headers={'Authorization':f'Bearer {token}'},
                    json=payload, timeout=12)
                result.raise_for_status()
            except httpx.HTTPError:
                vor_store.finish_email_delivery(reservation_id, 'failed_or_unknown')
                raise HTTPException(502,'Email provider unavailable') from None
            vor_store.finish_email_delivery(reservation_id, 'accepted')
            direction = 'outgoing'
        else:
            direction = 'simulated_outgoing'
    try:
        event_id = vor_store.add_event(body.vehicle_id, body.ticket_id, body.kind, body.text,'Alex',
                                       subject=subject,recipient=','.join(recipients) if body.kind=='email' else None,direction=direction)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {'id':event_id,'delivery':direction or 'internal','recipient_count':len(recipients),'recipients':recipients}


@router.post('/bookings',dependencies=[Depends(required)])
def create_booking(body: NewBooking, request: Request) -> dict:
    same_origin(request)
    try:
        pk=vor_store.add_booking(body.vehicle_id,body.kind,body.booked_date,body.garage)
    except (ValueError,OverflowError) as exc:
        raise HTTPException(422,str(exc)) from exc
    except Exception as exc:
        # Unique booking constraint, not an opaque 500.
        import sqlite3
        if isinstance(exc, sqlite3.IntegrityError):
            raise HTTPException(409,'This booking already exists') from exc
        raise
    return {'id':pk}


@router.post('/advance', dependencies=[Depends(required)])
def advance(body: NextStep, request: Request) -> dict:
    same_origin(request)
    try:
        vor_store.advance_workflow(body.vehicle_id,body.ticket_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {'ok':True}


@router.post('/scenario', dependencies=[Depends(required)])
def change_scenario(body: ChangeScenario, request: Request) -> dict:
    same_origin(request)
    try:
        vor_store.change_workflow_scenario(body.vehicle_id,body.ticket_id,body.scenario)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {'ok':True}


@router.post('/responsible', dependencies=[Depends(required)])
def set_responsible(body: ChangeResponsible, request: Request) -> dict:
    same_origin(request)
    try:
        vor_store.change_responsible(body.vehicle_id,body.name)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {'ok':True}


@router.post('/workshop', dependencies=[Depends(required)])
def set_workshop(body: ChangeWorkshop, request: Request) -> dict:
    same_origin(request)
    try:
        vor_store.change_workshop(body.vehicle_id, body.garage)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {'ok':True}


@router.post('/contacts',dependencies=[Depends(required)])
def create_contact(body: NewContact, request: Request) -> dict:
    same_origin(request)
    if not EMAIL_RE.fullmatch(body.email):
        raise HTTPException(422,'Invalid email')
    return {'id':vor_store.add_contact(body.name,body.email,body.role)}


@router.post('/subscribers',dependencies=[Depends(required)])
def update_subscriber(body: Subscribe, request: Request) -> dict:
    same_origin(request)
    try:
        vor_store.toggle_subscriber(body.vehicle_id,body.contact_id,body.subscribed)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {'ok':True}


@router.post('/contacts/{contact_id}/update', dependencies=[Depends(required)])
def edit_contact(contact_id: int, body: UpdateContact, request: Request) -> dict:
    same_origin(request)
    if not EMAIL_RE.fullmatch(body.email):
        raise HTTPException(422, 'Invalid email')
    try:
        vor_store.update_contact(contact_id, body.name, body.email, body.role)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {'ok': True}
