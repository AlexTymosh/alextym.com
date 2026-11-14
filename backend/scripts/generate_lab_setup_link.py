"""Explicit, local Owner-only generator for password setup/recovery links.

No automatic email. The one-time link is printed to the terminal ONLY after
successful Firebase generation and durable audit. Never paste it in Git/logs.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from app.security.lab_provisioning import (
    ProvisioningError,
    normalize_invitee_email,
)

from app.security.lab_setup_link import (
    FirestoreSetupIdentityStore,
    build_private_action_link,
    create_setup_identity,
    verify_existing_setup_identity,
)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate a private Portfolio Lab password setup link")
    p.add_argument("--email", required=True)
    p.add_argument("--project-id", required=True)
    p.add_argument("--origin", required=True, help="Approved website HTTPS origin")
    p.add_argument("--create-user", action="store_true", help="Create a new invited UID")
    p.add_argument("--apply", action="store_true", help="Enable remote Firebase operations")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        email = normalize_invitee_email(args.email)
        # Validate origin even in dry-run, without contacting Firebase.
        build_private_action_link(
            "https://example.firebaseapp.com/__/auth/action?mode=resetPassword&oobCode=" + "a" * 20,
            args.origin,
            "dry-run",
            allow_http_local=os.getenv("PORTFOLIO_LAB_ALLOW_LOCAL_HTTP") == "true",
        )
    except (ValueError, ProvisioningError) as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 2
    if not args.apply:
        print("DRY RUN: inputs validated. No Firebase/Firestore write or email.")
        return 0
    if os.getenv("PORTFOLIO_LAB_PROVISIONING_ENABLED") != "true":
        print("Denied: Owner-only provisioning switch is not enabled", file=sys.stderr)
        return 2
    project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    owner_uid = os.getenv("PORTFOLIO_LAB_OWNER_UID", "").strip()
    if not project_id or args.project_id != project_id or not owner_uid:
        print("Denied: project or pinned Owner UID mismatch", file=sys.stderr)
        return 2
    try:
        from firebase_admin import auth, firestore

        from app.security.firebase_identity import _firebase_app
        from scripts.provision_lab_identity import _AuthClient

        app = _firebase_app()
        client = _AuthClient(auth, app)
        store = firestore.client(app=app)
        setup_store = FirestoreSetupIdentityStore(store)
        now = int(time.time() * 1000)
        if args.create_user:
            identity = create_setup_identity(
                auth_client=client,
                identity_store=setup_store,
                actor_uid=owner_uid,
                email=email,
                now_ms=now,
            )
            user = auth.get_user(identity.uid, app=app)
        else:
            user = auth.get_user_by_email(email, app=app)
            snapshot = (
                store.collection("portfolio_lab_identities").document(user.uid).get(timeout=5.0)
            )
            verify_existing_setup_identity(
                auth_user=user,
                record=snapshot.to_dict() if snapshot.exists else None,
                owner_uid=owner_uid,
            )
        uid = user.uid
        if user.email is None or user.email.lower() != email:
            raise ProvisioningError("Firebase account email changed")
        link = auth.generate_password_reset_link(email, app=app)
        private_link = build_private_action_link(
            link,
            args.origin,
            uid,
            allow_http_local=os.getenv("PORTFOLIO_LAB_ALLOW_LOCAL_HTTP") == "true",
            emulator_host=os.getenv("FIREBASE_AUTH_EMULATOR_HOST"),
        )
        setup_store.record_link(user, owner_uid, private_link, now)
    except Exception:
        print(
            "Setup link not confirmed; inspect Auth UID and audit state before retrying. No link released.",
            file=sys.stderr,
        )
        return 1
    print(f"UID: {uid}")
    print("Sensitive one-time link; share privately, never log or commit:")
    print(private_link)
    print("No email was sent; no project grants were created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
