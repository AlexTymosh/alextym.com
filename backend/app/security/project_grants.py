"""Shared Portfolio Lab project grant policy, independent from demo business code.

Grant lookup is uncached so revocations apply to the next protected request.
Firestore is the authoritative control plane; absence or read failure never grants access.
"""

from __future__ import annotations

import os
import time
from typing import Any

from fastapi import HTTPException, Request

from app.security import firebase_identity

WORKFORCE_PROJECT_ID = "workforce_intelligence"


def admin_grant_allows(uid: str, project_id: str, record: Any, now_ms: int) -> bool:
    """The current Workforce member contract requires a project Admin grant.

    `Admin` here is a platform project capability, not a Workforce role or global
    Owner privilege. Reset must not be authorized by a `Test` grant.
    """
    if not uid or "/" in uid or not project_id or "/" in project_id:
        return False
    if not isinstance(record, dict) or type(now_ms) is not int:
        return False
    if (
        type(record.get("schema_version")) is not int
        or record["schema_version"] != 1
        or record.get("uid") != uid
        or record.get("project_id") != project_id
        or record.get("status") != "active"
        or record.get("role") != "Admin"
    ):
        return False
    expiry = record.get("expires_at_ms")
    if expiry is None:
        return "expires_at_ms" not in record
    return type(expiry) is int and 0 < expiry < 8_640_000_000_000_000 and now_ms < expiry


def grant_document(db: Any, project_id: str, uid: str) -> Any:
    """Unambiguous, project-scoped Firestore document path; never email-keyed."""
    if not uid or "/" in uid or not project_id or "/" in project_id:
        raise ValueError("Invalid grant identity")
    return (
        db.collection("portfolio_lab_projects")
        .document(project_id)
        .collection("grants")
        .document(uid)
    )


def load_project_grant(project_id: str, uid: str) -> dict | None:
    from firebase_admin import firestore

    db = firestore.client(app=firebase_identity._firebase_app())
    snapshot = grant_document(db, project_id, uid).get(timeout=5.0)
    return snapshot.to_dict() if snapshot.exists else None


def workforce_enabled() -> bool:
    return (
        os.getenv("PORTFOLIO_LAB_ENABLED") == "true"
        and os.getenv("WORKFORCE_INTELLIGENCE_ENABLED") == "true"
    )


def require_workforce_member(request: Request) -> dict:
    """Host-owned security dependency mounted on every Workforce API route."""
    if not workforce_enabled():
        raise HTTPException(404, "Not found")
    identity = firebase_identity.require_lab_identity(request)
    uid = identity["uid"]
    owner_uid = os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
    if uid == owner_uid:
        # This UID has already been independently verified by require_lab_identity.
        return identity
    try:
        grant = load_project_grant(WORKFORCE_PROJECT_ID, uid)
    except Exception as exc:
        raise HTTPException(503, "Project access unavailable") from exc
    if not admin_grant_allows(uid, WORKFORCE_PROJECT_ID, grant, int(time.time() * 1000)):
        raise HTTPException(403, "Project access denied")
    return identity
