"""Manual Owner-only recovery of a stuck `reset_pending` credential.

No public endpoint, passwords, emails or grants. Must target an explicit Firebase
project and be run using restricted local operator credentials.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from app.security.lab_provisioning import ProvisioningError
from app.security.lab_reset_repair import FirestoreResetRepairStore, repair_interrupted_reset


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Fail-closed repair of an interrupted Lab password reset"
    )
    p.add_argument("--uid", required=True, help="Exact Firebase UID (not email)")
    p.add_argument("--project-id", required=True, help="Explicit Firebase project ID")
    p.add_argument("--apply", action="store_true", help="Perform auditable remote changes")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    uid = args.uid.strip()
    if not uid or uid != args.uid or "/" in uid:
        print("Invalid UID", file=sys.stderr)
        return 2
    if not args.apply:
        print("DRY RUN: no Firebase/Firestore calls. --apply is required.")
        return 0
    if os.getenv("PORTFOLIO_LAB_PROVISIONING_ENABLED") != "true":
        print("Denied: provisioning operator gate disabled", file=sys.stderr)
        return 2
    project = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    owner = os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
    if not project or project != args.project_id or not owner or uid == owner:
        print("Denied: pinned Firebase project/Owner UID required", file=sys.stderr)
        return 2
    try:
        from firebase_admin import auth, firestore

        from app.security.firebase_identity import _firebase_app

        app = _firebase_app()

        class Client:
            def get_user(self, user_uid: str):
                return auth.get_user(user_uid, app=app)

            def revoke_refresh_tokens(self, user_uid: str) -> None:
                auth.revoke_refresh_tokens(user_uid, app=app)

        repair_interrupted_reset(
            auth_client=Client(),
            identity_store=FirestoreResetRepairStore(firestore.client(app=app)),
            owner_uid=owner,
            uid=uid,
            now_ms=int(time.time() * 1000),
        )
    except ProvisioningError as exc:
        print(f"Repair declined: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("Repair failed; verify project state without revealing credentials", file=sys.stderr)
        return 1
    print("Reset repaired: password login remains disabled; issue a fresh Owner setup link.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
