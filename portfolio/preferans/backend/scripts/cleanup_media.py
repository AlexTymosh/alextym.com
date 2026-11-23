"""Explicit, bounded removal of expired Preferans signalling metadata.

This is NOT a scheduled task and never enables paid Firestore TTL. It is a
manual operator action requiring both --apply and --confirm-project-id.
No SDP, ICE, UIDs or tokens are printed. A bounded scan protects £0 usage.
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime


def _expired(data: dict | None, now: datetime) -> bool:
    if not isinstance(data, dict):
        return False
    value = data.get("expires_at")
    return isinstance(value, datetime) and value.tzinfo is not None and value <= now


def cleanup(db, *, now: datetime, apply: bool, max_rooms: int, max_deletes: int) -> dict:
    """Scan bounded collection groups by room, avoiding wildcard cross-project TTL."""
    if apply and not callable(getattr(db, "write_option", None)):
        raise RuntimeError("Firestore client must provide conditional write_option")
    checked = 0
    expired = 0
    deleted = 0
    for snap in db.collection("preferans_rooms").limit(max_rooms).stream(timeout=20):
        checked += 1
        media = snap.reference.collection("preferans_media").document("current")
        current = media.get(timeout=5)
        if current.exists and _expired(current.to_dict(), now):
            expired += 1
            if apply and deleted < max_deletes:
                media.delete(
                    option=db.write_option(last_update_time=current.update_time), timeout=5
                )
                deleted += 1
        for op in (
            snap.reference.collection("preferans_media_ops").limit(max_deletes).stream(timeout=10)
        ):
            if _expired(op.to_dict(), now):
                expired += 1
                if apply and deleted < max_deletes:
                    op.reference.delete(
                        option=db.write_option(last_update_time=op.update_time), timeout=5
                    )
                    deleted += 1
        if apply and deleted >= max_deletes:
            break
    return {"rooms_scanned": checked, "expired_found": expired, "deleted": deleted}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune expired Preferans signalling metadata")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--max-rooms", type=int, default=20)
    parser.add_argument("--max-deletes", type=int, default=100)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-project-id", default="")
    args = parser.parse_args()
    if not 1 <= args.max_rooms <= 200 or not 1 <= args.max_deletes <= 1000:
        parser.error("Limits must be between 1 and 200 rooms / 1000 deletes")
    if args.apply and args.confirm_project_id != args.project_id:
        parser.error("--apply requires --confirm-project-id exactly matching --project-id")
    if not args.project_id or "/" in args.project_id or args.project_id.startswith("-"):
        parser.error("Invalid project ID")
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") is None and not os.getenv(
        "FIRESTORE_EMULATOR_HOST"
    ):
        print(
            "ADC credentials or a Firestore Emulator are required; no fallback to an anonymous account"
        )
        return 2
    from firebase_admin import firestore, initialize_app

    app = initialize_app(options={"projectId": args.project_id}, name="preferans-maintenance")
    db = firestore.client(app=app)
    result = cleanup(
        db,
        now=datetime.now(UTC),
        apply=args.apply,
        max_rooms=args.max_rooms,
        max_deletes=args.max_deletes,
    )
    print(f"mode={'APPLY' if args.apply else 'DRY-RUN'} project={args.project_id}")
    print(
        f"rooms_scanned={result['rooms_scanned']} expired_found={result['expired_found']} deleted={result['deleted']}"
    )
    print("This scan is bounded and is NOT evidence that all expired documents were removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
