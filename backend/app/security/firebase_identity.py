"""Independent Firebase ID-token verification at the direct FastAPI origin.

The browser's Next.js HttpOnly cookie is scoped to the website origin and is
not forwarded to Render as a credential. Protected backend calls must present
an independently verified Firebase ID token (Bearer) or session cookie
(FirebaseSession scheme, forwarded only by the Next.js BFF).

PR 2 permits the pinned Owner UID or a durable admitted UID with a valid
initial-credential policy. PR 3 will add project grants and capabilities;
identity admission must never become project authorization.
"""

from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache

from fastapi import HTTPException, Request

from app.security.lab_admission import (
    OAUTH_PROVIDERS,
    admission_decision,
    oauth_subject,
    sign_in_provider,
)


@lru_cache(maxsize=1)
def _firebase_app():
    import firebase_admin
    from firebase_admin import credentials

    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    if not project_id:
        raise RuntimeError("Firebase project is not configured")
    emulator_hosts = [
        os.getenv(name) for name in ("FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST")
    ]
    if any(emulator_hosts):
        if (
            os.getenv("RENDER")
            or not project_id.startswith("demo-")
            or not all(
                host and re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", host) for host in emulator_hosts
            )
        ):
            raise RuntimeError("Both Firebase emulators must use a local demo project")

        from google.auth.credentials import AnonymousCredentials

        class EmulatorCredential(credentials.Base):
            def get_credential(self):
                return AnonymousCredentials()

    try:
        app = firebase_admin.get_app("portfolio-lab")
    except ValueError:
        raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
        if any(emulator_hosts):
            credential = EmulatorCredential()
        elif raw:
            credential = credentials.Certificate(json.loads(raw))
            if credential.project_id != project_id:
                raise RuntimeError("Firebase credential project does not match configuration")
        else:
            credential = credentials.ApplicationDefault()
        app = firebase_admin.initialize_app(
            credential, {"projectId": project_id}, name="portfolio-lab"
        )
    if app.project_id != project_id:
        raise RuntimeError("Firebase project does not match configuration")
    return app


def verify_id_token(token: str) -> dict:
    """Verify real signature, project ID, expiry and revocation, not token payload text."""
    from firebase_admin import auth

    return auth.verify_id_token(token, app=_firebase_app(), check_revoked=True)


def verify_session_cookie(session_cookie: str) -> dict:
    """Independently verify a Firebase session cookie received via trusted BFF.

    Treat the cookie as a bearer credential: a direct Render caller still needs
    its valid signed value. Never trust a website Origin, Host or user-supplied UID.
    """
    from firebase_admin import auth

    return auth.verify_session_cookie(session_cookie, app=_firebase_app(), check_revoked=True)


def load_lab_identity(uid: str) -> dict | None:
    """Fetch durable UID admission; never infer grants from email or token alone."""
    from firebase_admin import firestore

    snapshot = (
        firestore.client(app=_firebase_app())
        .collection("portfolio_lab_identities")
        .document(uid)
        .get(timeout=5.0)
    )
    return snapshot.to_dict() if snapshot.exists else None


def has_current_oauth_subject(uid: str, provider: str, subject: str | None) -> bool:
    from firebase_admin import auth

    if not subject:
        return False
    user = auth.get_user(uid, app=_firebase_app())
    return not user.disabled and any(
        item.provider_id == provider and item.uid == subject for item in user.provider_data
    )


def require_lab_identity(request: Request) -> dict:
    """Verify identity, current admission and initial-password policy."""
    if os.getenv("PORTFOLIO_LAB_ENABLED", "false").lower() != "true":
        raise HTTPException(404, "Not found")
    expected_uid = os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
    if not expected_uid:
        raise HTTPException(503, "Lab unavailable")
    scheme, sep, token = request.headers.get("authorization", "").partition(" ")
    credential_kind = scheme.lower()
    if (
        not sep
        or credential_kind not in {"bearer", "firebasesession"}
        or not (1 <= len(token) <= 8192)
    ):
        raise HTTPException(401, "Verified Firebase credential required")
    try:
        # Explicit, non-interchangeable token types. In particular, an invalid
        # ID token never falls back to session-cookie verification and vice versa.
        if credential_kind == "bearer":
            claims = verify_id_token(token)
        else:
            claims = verify_session_cookie(token)
    except Exception as exc:
        # No exception or token data is logged/returned; fail closed on SDK errors.
        raise HTTPException(401, "Invalid identity") from exc
    uid = claims.get("uid")
    if not isinstance(uid, str) or not uid or "/" in uid:
        raise HTTPException(403, "Access denied")
    provider = sign_in_provider(claims)
    if uid == expected_uid and provider == "password":
        return {"uid": uid}
    if provider != "password" and provider not in OAUTH_PROVIDERS:
        raise HTTPException(403, "Access denied")
    subject = oauth_subject(claims, provider)
    try:
        identity_record = load_lab_identity(uid)
        decision = admission_decision(
            uid,
            expected_uid,
            provider,
            identity_record,
            int(time.time() * 1000),
            claims.get("auth_time"),
            subject,
        )
        if (
            decision == "allowed"
            and provider != "password"
            and not has_current_oauth_subject(uid, provider, subject)
        ):
            decision = "denied"
    except Exception as exc:
        raise HTTPException(503, "Admission unavailable") from exc
    if decision != "allowed":
        raise HTTPException(403, "Access denied")
    return {"uid": uid}


# Backward-compatible name for existing security unit imports; new code uses
# the explicit admission-aware dependency.
require_owner_identity = require_lab_identity
