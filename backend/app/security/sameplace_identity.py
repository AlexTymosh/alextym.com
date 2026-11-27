"""Host-owned credential verification and Firebase composition; no room policy."""

import os
import time
from fastapi import HTTPException, Request
from app.security import firebase_identity as firebase
from app.security.lab_admission import (
    OAUTH_PROVIDERS,
    admission_decision,
    oauth_subject,
    sign_in_provider,
)


def sameplace_enabled() -> bool:
    return os.getenv("PORTFOLIO_LAB_ENABLED") == "true" and os.getenv("SAMEPLACE_ENABLED") == "true"


def require_sameplace_identity(request: Request) -> dict:
    if not sameplace_enabled():
        raise HTTPException(404, "Not found")
    owner = os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
    if not owner:
        raise HTTPException(503, "IDENTITY_UNAVAILABLE")
    scheme, sep, token = request.headers.get("authorization", "").partition(" ")
    if (
        not sep
        or scheme.lower() not in {"bearer", "firebasesession"}
        or not 1 <= len(token) <= 8192
    ):
        raise HTTPException(401, "AUTH_REQUIRED")
    try:
        claims = (
            firebase.verify_id_token(token)
            if scheme.lower() == "bearer"
            else firebase.verify_session_cookie(token)
        )
    except Exception as exc:
        raise HTTPException(401, "AUTH_REQUIRED") from exc
    uid = claims.get("uid")
    provider = sign_in_provider(claims)
    if (
        not isinstance(uid, str)
        or not 1 <= len(uid) <= 128
        or "/" in uid
        or any(ord(c) < 32 for c in uid)
    ):
        raise HTTPException(403, "ACCESS_DENIED")
    if provider != "password" and provider not in OAUTH_PROVIDERS:
        raise HTTPException(403, "ACCESS_DENIED")
    email = claims.get("email")
    verified_email = (
        email
        if claims.get("email_verified") is True and isinstance(email, str) and 0 < len(email) <= 254
        else None
    )
    try:
        subject = oauth_subject(claims, provider)
        if uid == owner and provider == "password":
            return {"uid": uid, "verified_email": verified_email, "platform_owner": True}
        record = firebase.load_lab_identity(uid)
        if record is None and uid != owner:
            # A new, verified Firebase account may only prove identity here.
            # No global admission/grant is created. Object membership is checked in the project.
            allowed = verified_email is not None
        else:
            # Never use the room-only route to bypass an explicit Lab denial, password expiry or provider binding.
            allowed = (
                admission_decision(
                    uid,
                    owner,
                    provider,
                    record,
                    int(time.time() * 1000),
                    claims.get("auth_time"),
                    subject,
                )
                == "allowed"
            )
        if allowed and provider != "password":
            allowed = firebase.has_current_oauth_subject(uid, provider, subject)
    except Exception as exc:
        raise HTTPException(503, "IDENTITY_UNAVAILABLE", headers={"Retry-After": "60"}) from exc
    if not allowed:
        raise HTTPException(403, "ACCESS_DENIED")
    return {"uid": uid, "verified_email": verified_email, "platform_owner": uid == owner}


def sameplace_database():
    from firebase_admin import firestore

    return firestore.client(app=firebase._firebase_app()), firestore.transactional
