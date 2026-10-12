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
    recipient: str | None = Field(default=None,max_length=254)
    subject: str | None = Field(default=None,max_length=200)

class NewBooking(BaseModel):
    vehicle_id: int
    kind: Literal['MOT','Inspection','Service']
    booked_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    garage: str = Field(min_length=1,max_length=100)

class NextStep(BaseModel):
    vehicle_id: int
    ticket_id: str

class NewContact(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    email: str = Field(min_length=3,max_length=254)
    role: Literal['internal','external']

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


EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


@router.post('/messages', dependencies=[Depends(required)])
def create_message(body: NewMessage, request: Request) -> dict:
    same_origin(request)
    recipient = (body.recipient or '').strip().lower()
    direction = None
    try:
        registration = vor_store.validate_vehicle_ticket(body.vehicle_id, body.ticket_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    subject = body.subject
    if body.kind == 'email':
        prefix = f'[{registration}]' + (f'[{body.ticket_id}]' if body.ticket_id else '')
        subject = f'{prefix} {body.subject or "Fleet update"}'
        if not EMAIL_RE.fullmatch(recipient):
            raise HTTPException(422,'Valid email recipient required')
        real = os.getenv('VOR_DEMO_SEND_REAL_EMAIL','false').lower() == 'true'
        if real:
            allowed = {x.strip().lower() for x in os.getenv('VOR_DEMO_ALLOWED_RECIPIENTS','').split(',') if x.strip()}
            if recipient not in allowed:
                raise HTTPException(403,'Recipient is not on the allowlist')
            limit = max(1,min(int(os.getenv('VOR_DEMO_EMAIL_LIMIT','15')),30))
            if vor_store.email_count_today() >= limit:
                raise HTTPException(429,'Daily email limit reached')
            token = os.getenv('RESEND_API_KEY','')
            from_email = os.getenv('VOR_DEMO_FROM_EMAIL','')
            if not token or not from_email:
                raise HTTPException(503,'Real email settings are incomplete')
            try:
                result = httpx.post('https://api.resend.com/emails',
                    headers={'Authorization':f'Bearer {token}'},
                    json={'from':from_email,'to':[recipient], 'subject':subject, 'text':body.text}, timeout=12)
                result.raise_for_status()
            except httpx.HTTPError:
                raise HTTPException(502,'Email provider unavailable') from None
            direction = 'outgoing'
        else:
            direction = 'simulated_outgoing'
    try:
        event_id = vor_store.add_event(body.vehicle_id, body.ticket_id, body.kind, body.text,'Alex',
                                       subject=subject,recipient=recipient if body.kind=='email' else None,direction=direction)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {'id':event_id,'delivery':direction or 'internal'}


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
