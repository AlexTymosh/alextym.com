"""Explicit local Owner-only command for initial-password Firebase provisioning.

Run with --apply and a matching --project-id. No public route, automatic emails,
credentials in command-line arguments, or implicit grants are introduced.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from getpass import getpass

from app.security.lab_provisioning import (
    FirestoreIdentityStore,
    ProvisioningError,
    normalize_invitee_email,
    provision_initial_identity,
    validate_initial_password,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision a new Portfolio Lab identity")
    parser.add_argument("--email", required=True, help="New email; existing users are rejected")
    parser.add_argument("--days", type=int, default=90, help="Initial password validity: 1–90")
    parser.add_argument("--project-id", required=True, help="Explicit Firebase target project ID")
    parser.add_argument("--apply", action="store_true", help="Perform remote writes")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        normalize_invitee_email(args.email)
        # Validate duration before loading any Firebase credentials.
        validate_initial_password("x" * 16, args.days)
    except ValueError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 2

    if not args.apply:
        print("DRY RUN: input validated. No Firebase calls, email or project grants.")
        return 0

    if os.getenv("PORTFOLIO_LAB_PROVISIONING_ENABLED") != "true":
        print("Denied: PORTFOLIO_LAB_PROVISIONING_ENABLED is not true", file=sys.stderr)
        return 2
    target = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    actor_uid = os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
    if not target or args.project_id != target or not actor_uid:
        print("Denied: project ID or pinned Owner UID is not configured", file=sys.stderr)
        return 2

    password = getpass("Initial password (not echoed): ")
    confirmation = getpass("Confirm initial password: ")
    if password != confirmation:
        print("Passwords do not match", file=sys.stderr)
        return 2
    try:
        validate_initial_password(password, args.days)
    except ValueError as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 2
    del confirmation

    try:
        from firebase_admin import firestore

        from app.security.firebase_identity import _firebase_app

        app = _firebase_app()
        from firebase_admin import auth

        outcome = provision_initial_identity(
            auth_client=_AuthClient(auth, app),
            identity_store=FirestoreIdentityStore(firestore.client(app=app)),
            actor_uid=actor_uid,
            email=args.email,
            password=password,
            days=args.days,
            now_ms=int(time.time() * 1000),
        )
    except ProvisioningError as exc:
        print(f"Provisioning failed: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "Provisioning failed: check configuration and investigate server logs", file=sys.stderr
        )
        return 1
    finally:
        del password

    print(f"New UID: {outcome.uid}")
    print(f"Initial password expires at Unix milliseconds: {outcome.expires_at_ms}")
    print("No email was sent and no project access was granted.")
    print("Deliver the initial password separately over a secure channel.")
    return 0


class _AuthClient:
    """Bind Firebase Admin Auth functions to the configured, named app."""

    def __init__(self, module: object, app: object) -> None:
        self.module = module
        self.app = app

    def create_user(self, **kwargs):
        return self.module.create_user(app=self.app, **kwargs)

    def update_user(self, uid: str, **kwargs):
        return self.module.update_user(uid, app=self.app, **kwargs)

    def delete_user(self, uid: str):
        return self.module.delete_user(uid, app=self.app)


if __name__ == "__main__":
    raise SystemExit(main())
