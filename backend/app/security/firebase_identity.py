"""Independent Firebase ID-token verification at the direct FastAPI origin.

The browser's Next.js HttpOnly cookie is scoped to the website origin and is
not forwarded to Render as a credential. Protected backend calls must present
an independently verifiable Firebase ID token in Authorization: Bearer.

PR 2 permits only the pinned Owner UID. PR 3 will add durable project grants;
this module must never become a general "authenticated means authorized" bypass.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

from fastapi import HTTPException, Request


@lru_cache(maxsize=1)
def _firebase_app():
    import firebase_admin
    from firebase_admin import credentials

    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    if not project_id:
        raise RuntimeError("Firebase project is not configured")
    try:
        return firebase_admin.get_app("portfolio-lab")
    except ValueError:
        raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
        credential = (
            credentials.Certificate(json.loads(raw)) if raw else credentials.ApplicationDefault()
        )
        return firebase_admin.initialize_app(
            credential, {"projectId": project_id}, name="portfolio-lab"
        )


def verify_id_token(token: str) -> dict:
    """Verify real signature, project ID, expiry and revocation, not token payload text."""
    from firebase_admin import auth

    return auth.verify_id_token(token, app=_firebase_app(), check_revoked=True)


def require_owner_identity(request: Request) -> dict:
    """Temporary narrow identity probe; never protects real project operations."""
    if os.getenv("PORTFOLIO_LAB_ENABLED", "false").lower() != "true":
        raise HTTPException(404, "Not found")
    expected_uid = os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
    if not expected_uid:
        raise HTTPException(503, "Lab unavailable")
    scheme, sep, token = request.headers.get("authorization", "").partition(" ")
    if not sep or scheme.lower() != "bearer" or not (1 <= len(token) <= 8192):
        raise HTTPException(401, "Bearer Firebase ID token required")
    try:
        claims = verify_id_token(token)
    except Exception as exc:
        # No exception or token data is logged/returned; fail closed on SDK errors.
        raise HTTPException(401, "Invalid identity") from exc
    if claims.get("uid") != expected_uid:
        raise HTTPException(403, "Access denied")
    return {"uid": expected_uid}
