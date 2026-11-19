"""Explicit operator CLI for a single fixed Workforce membership capability.

Administrative Firebase credentials and the configured global Owner UID are
required. This command does not create an Auth account or send login credentials.
Dry-run is the default. Writes include an independent central security audit.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from app.security.firebase_identity import _firebase_app
from app.security.lab_provisioning import MAX_INITIAL_PASSWORD_DAYS, MILLIS_PER_DAY
from app.security.project_grants import WORKFORCE_PROJECT_ID, grant_document


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage one Workforce project grant by Firebase UID"
    )
    parser.add_argument("action", choices=["admit-and-grant", "grant", "revoke"])
    parser.add_argument("--uid", required=True, help="Exact Firebase Authentication UID")
    parser.add_argument(
        "--apply", action="store_true", help="Actually commit grant and audit writes"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    uid = args.uid
    if not uid or len(uid) > 128 or "/" in uid or uid in {".", ".."}:
        print("Invalid Firebase UID", file=sys.stderr)
        return 2
    owner_uid = os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
    if not owner_uid:
        print("PORTFOLIO_LAB_OWNER_UID is required", file=sys.stderr)
        return 2
    if uid == owner_uid:
        print("The pinned Owner does not require a project grant", file=sys.stderr)
        return 2
    if not args.apply:
        print(f"DRY RUN: {args.action} {WORKFORCE_PROJECT_ID} for UID {uid}")
        print("Supply --apply from the trusted operator environment to perform the write")
        return 0

    from firebase_admin import auth, firestore

    try:
        app = _firebase_app()
        db = firestore.client(app=app)
        admission_ref = db.collection("portfolio_lab_identities").document(uid)
        if args.action != "revoke":
            user = auth.get_user(uid, app=app)
            if user.disabled or not user.email:
                raise ValueError("Enabled email/password Auth account required")
            snapshot = admission_ref.get(timeout=5.0)
            current = snapshot.to_dict() if snapshot.exists else None
            if args.action == "admit-and-grant":
                if snapshot.exists:
                    raise ValueError("Admission already exists: use grant action")
            elif (
                not isinstance(current, dict)
                or current.get("uid") != uid
                or current.get("status") != "active"
                or current.get("schema_version") != 1
            ):
                raise ValueError("Active platform admission record required")

        ref = grant_document(db, WORKFORCE_PROJECT_ID, uid)
        event = db.collection("portfolio_lab_grant_events").document()
        now = int(time.time() * 1000)
        record = {
            "schema_version": 1,
            "project_id": WORKFORCE_PROJECT_ID,
            "uid": uid,
            "status": "revoked" if args.action == "revoke" else "active",
            "role": "Admin",
            "updated_at_ms": now,
        }
        batch = db.batch()
        if args.action == "admit-and-grant":
            # The Owner has independently created and checked the Auth account.
            # Apply the shared initial-password validity limit.
            batch.create(
                admission_ref,
                {
                    "schema_version": 1,
                    "uid": uid,
                    "status": "active",
                    "password_state": "initial",
                    "initial_password_expires_at_ms": now
                    + MAX_INITIAL_PASSWORD_DAYS * MILLIS_PER_DAY,
                },
            )
        batch.set(ref, record)
        batch.create(
            event,
            {
                "schema_version": 1,
                "project_id": WORKFORCE_PROJECT_ID,
                "uid": uid,
                "action": args.action,
                "actor_uid": owner_uid,
                "created_at_ms": now,
            },
        )
        batch.commit()
    except Exception:
        # Avoid printing SDK/service-account details to consoles or CI logs.
        print("Grant operation failed; verify credentials and target admission", file=sys.stderr)
        return 1
    print(f"Committed and audited: {args.action} {WORKFORCE_PROJECT_ID} for UID {uid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
