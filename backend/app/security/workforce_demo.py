"""Scoped password-demo sessions for Workforce, independent of Firebase.

The password is shared with the Fleet demo through VOR_DEMO_PASSWORD; sessions
are not. Authentication is enforced by FastAPI even on direct Render requests.
This is deliberately NOT intended for real workforce or personal data.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

SESSION_TTL = 8 * 3600
_ATTEMPT_WINDOW = 60
_MAX_ATTEMPTS = 8
_attempts: dict[str, list[float]] = defaultdict(list)
router = APIRouter(prefix="/workforce-access", tags=["Workforce demo access"])


class Login(BaseModel):
    password: str = Field(min_length=1, max_length=128)


def enabled() -> bool:
    return os.getenv("WORKFORCE_INTELLIGENCE_ENABLED") == "true"


@lru_cache(maxsize=2)
def _derive_key(password: str) -> bytes:
    """Derive a purpose-specific signing key using a slow password KDF."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        b"workforce-demo:session:v1",
        600_000,
        dklen=32,
    )


def _key() -> bytes | None:
    password = os.getenv("VOR_DEMO_PASSWORD", "")
    if not password:
        return None
    # Cache the expensive KDF per configured password; rotation remains effective.
    return _derive_key(password)


def _signature(issued: str, key: bytes) -> str:
    return hmac.new(key, f"workforce:v1:{issued}".encode(), hashlib.sha256).hexdigest()


def _now() -> float:
    return time.time()


def issue_session() -> str:
    key = _key()
    if key is None:
        raise HTTPException(503, "Demo password is not configured")
    issued = str(int(_now()))
    return f"v1.{issued}.{_signature(issued, key)}"


def valid_session(authorization: str | None) -> bool:
    if not enabled() or not authorization or not authorization.startswith("WorkforceDemo "):
        return False
    key = _key()
    if key is None:
        return False
    try:
        version, issued, signature = authorization[len("WorkforceDemo ") :].split(".")
        now = _now()
        stamp = int(issued)
        if version != "v1" or stamp > now or stamp + SESSION_TTL <= now:
            return False
        return hmac.compare_digest(signature, _signature(issued, key))
    except (ValueError, TypeError):
        return False


def require_workforce_member(request: Request) -> None:
    if not enabled():
        raise HTTPException(404, "Demo disabled")
    if not valid_session(request.headers.get("authorization")):
        raise HTTPException(401, "Password required")
    request.state.workforce_uid = "demo-member"


@router.post("/login")
def login(body: Login, request: Request, response: Response) -> dict[str, str | int]:
    response.headers["Cache-Control"] = "no-store"
    if not enabled():
        raise HTTPException(404, "Demo disabled")
    configured = os.getenv("VOR_DEMO_PASSWORD", "")
    if not configured:
        raise HTTPException(503, "Demo password is not configured")
    # Bound memory even under unauthenticated scanning; the CDN/WAF remains
    # responsible for distributed and cross-worker rate limits.
    peer = request.client.host if request.client else "unknown"
    now = time.monotonic()
    if len(_attempts) > 4096:
        _attempts.clear()
    recent = [stamp for stamp in _attempts.get(peer, ()) if now - stamp < _ATTEMPT_WINDOW]
    if len(recent) >= _MAX_ATTEMPTS:
        _attempts[peer] = recent
        raise HTTPException(429, "Too many attempts. Retry in one minute.")
    if not secrets.compare_digest(body.password, configured):
        recent.append(now)
        _attempts[peer] = recent
        raise HTTPException(401, "Incorrect password")
    _attempts.pop(peer, None)
    return {"session": issue_session(), "expires_in": SESSION_TTL}


@router.get("/session")
def session(request: Request, response: Response) -> dict[str, bool]:
    response.headers["Cache-Control"] = "no-store"
    if not enabled():
        raise HTTPException(404, "Demo disabled")
    return {"authenticated": valid_session(request.headers.get("authorization"))}
