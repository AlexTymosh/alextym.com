"""Shared HTTP authentication and origin dependencies for Fleet routers.

Keep FastAPI-specific checks here, not in a sibling route module. Preserve
legacy cookie, error status, origin policy, and session signature contracts.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

COOKIE = "vor_demo_session"
SESSION_TTL = 8 * 3600


def enabled() -> bool:
    return os.getenv("VOR_DEMO_ENABLED", "false").lower() == "true"


def secret() -> bytes:
    return hashlib.sha256(
        ("alextym-vor-demo:v1:" + os.getenv("VOR_DEMO_PASSWORD", "")).encode()
    ).digest()


def sign(payload: str) -> str:
    return hmac.new(secret(), payload.encode(), hashlib.sha256).hexdigest()


def session_valid(request: Request) -> bool:
    cookie = request.cookies.get(COOKIE, "")
    try:
        started, signature = cookie.split(".", 1)
        ts = int(started)
        return (ts <= time.time() < ts + SESSION_TTL) and hmac.compare_digest(
            signature, sign(started)
        )
    except (ValueError, TypeError):
        return False


def required(request: Request) -> None:
    if not enabled():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo disabled")
    if not session_valid(request):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password required")


def same_origin(request: Request) -> None:
    origin = request.headers.get("origin", "")
    # Next rewrite forwards Host/Origin; ensure browser POSTs originate from the displayed site.
    if origin:
        origin_host = urlsplit(origin).netloc.lower()
        forwarded_host = (
            (request.headers.get("x-forwarded-host") or request.headers.get("host") or "")
            .split(",")[0]
            .strip()
            .lower()
        )
        if origin_host != forwarded_host:
            # In some reverse proxy setups Host is the private backend while the browser origin is the frontend.
            trusted = {
                value.strip().lower()
                for value in os.getenv(
                    "VOR_DEMO_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
                ).split(",")
                if value.strip()
            }
            if origin.lower() not in trusted:
                raise HTTPException(403, "Invalid origin")
