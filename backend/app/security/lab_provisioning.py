"""Owner-initiated Firebase account provisioning; no HTTP endpoint or email send.

This module deliberately separates identity admission from project grants. New
accounts start disabled and become usable only after a durable, audited UID
record has been activated. Partial failures leave admission closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

MILLIS_PER_DAY = 24 * 60 * 60 * 1000
MAX_INITIAL_PASSWORD_DAYS = 90


class ProvisioningError(RuntimeError):
    """A safe-to-display operational failure without provider exception details."""


class IdentityStore(Protocol):
    def create_invited(self, uid: str, record: dict[str, Any], actor_uid: str) -> None: ...

    def activate(self, uid: str, activated_at_ms: int, actor_uid: str) -> None: ...


@dataclass(frozen=True)
class ProvisionedIdentity:
    uid: str
    expires_at_ms: int


def normalize_invitee_email(email: str) -> str:
    """Conservative address gate; Firebase performs authoritative validation."""
    if not isinstance(email, str):
        raise ValueError("A valid email address is required")
    normalized = email.strip().lower()
    if (
        len(normalized) > 254
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized)
        or any(ord(character) < 33 or ord(character) == 127 for character in normalized)
    ):
        raise ValueError("A valid email address is required")
    return normalized


def validate_initial_password(password: str, days: int) -> None:
    if type(days) is not int or not 1 <= days <= MAX_INITIAL_PASSWORD_DAYS:
        raise ValueError("Initial password validity must be 1–90 days")
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError("Initial password must have 12–128 characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise ValueError("Initial password contains invalid control characters")


def provision_initial_identity(
    *,
    auth_client: Any,
    identity_store: IdentityStore,
    actor_uid: str,
    email: str,
    password: str,
    days: int,
    now_ms: int,
) -> ProvisionedIdentity:
    """Provision a *new* UID. Never overwrite existing Firebase accounts.

    No email is sent, no grant is made, and a failure never returns plaintext
    credentials or provider error details. The caller must handle delivery.
    """
    normalized_email = normalize_invitee_email(email)
    validate_initial_password(password, days)
    if not isinstance(actor_uid, str) or not actor_uid or "/" in actor_uid:
        raise ValueError("A pinned Owner UID is required")
    if (
        type(now_ms) is not int
        or now_ms <= 0
        or now_ms + days * MILLIS_PER_DAY >= 8_640_000_000_000_000
    ):
        raise ValueError("A trusted timestamp is required")

    try:
        # A pre-existing email is never silently adopted or re-bound to a UID.
        user = auth_client.create_user(email=normalized_email, password=password, disabled=True)
    except Exception as exc:
        raise ProvisioningError(
            "Firebase user creation failed or the account already exists; no existing account was changed"
        ) from exc

    uid = getattr(user, "uid", None)
    if not isinstance(uid, str) or not uid or "/" in uid:
        # Do not activate an identity without a safe document key.
        if isinstance(uid, str) and uid:
            try:
                auth_client.delete_user(uid)
            except Exception:
                pass
        raise ProvisioningError("Firebase returned an invalid UID; inspect disabled accounts")

    expiry = now_ms + days * MILLIS_PER_DAY
    record = {
        "schema_version": 1,
        "uid": uid,
        "status": "invited",
        "password_state": "initial",
        "initial_password_expires_at_ms": expiry,
        "provisioned_at_ms": now_ms,
        "provisioned_by_uid": actor_uid,
    }
    try:
        identity_store.create_invited(uid, record, actor_uid)
    except Exception as exc:
        # The account was created disabled. A best-effort deletion limits
        # orphans, but an ambiguous Firestore outcome remains fail-closed.
        try:
            auth_client.delete_user(uid)
        except Exception:
            pass
        raise ProvisioningError(
            "Admission record creation failed; inspect Firebase for a disabled orphan"
        ) from exc

    try:
        auth_client.update_user(uid, disabled=False)
    except Exception as exc:
        # Firestore still says 'invited', so even an ambiguous enable outcome
        # cannot grant application admission.
        raise ProvisioningError(
            "Account activation was not confirmed; identity remains invited, inspect UID manually"
        ) from exc

    try:
        identity_store.activate(uid, now_ms, actor_uid)
    except Exception as exc:
        # No email was sent. Firestore activation may be ambiguous if the
        # acknowledgement was lost; reconcile before delivering credentials.
        raise ProvisioningError(
            "Admission activation was not confirmed; reconcile UID before credential delivery"
        ) from exc

    return ProvisionedIdentity(uid=uid, expires_at_ms=expiry)


class FirestoreIdentityStore:
    """Atomically commit identity state and its Owner action audit event."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def create_invited(self, uid: str, record: dict[str, Any], actor_uid: str) -> None:
        identity = self.client.collection("portfolio_lab_identities").document(uid)
        event = self.client.collection("portfolio_lab_invitation_events").document(str(uuid4()))
        batch = self.client.batch()
        batch.create(identity, record)
        batch.create(
            event,
            {
                "schema_version": 1,
                "uid": uid,
                "actor_uid": actor_uid,
                "action": "initial_password_provisioning_started",
                "created_at_ms": record["provisioned_at_ms"],
            },
        )
        batch.commit()

    def activate(self, uid: str, activated_at_ms: int, actor_uid: str) -> None:
        from google.cloud import firestore as google_firestore

        identity = self.client.collection("portfolio_lab_identities").document(uid)
        event = self.client.collection("portfolio_lab_invitation_events").document(str(uuid4()))

        @google_firestore.transactional
        def write(transaction):
            snapshot = identity.get(transaction=transaction)
            record = snapshot.to_dict() or {}
            if (
                type(record.get("schema_version")) is not int
                or record["schema_version"] != 1
                or record.get("uid") != uid
                or record.get("status") != "invited"
                or record.get("password_state") != "initial"
                or record.get("provisioned_by_uid") != actor_uid
                or record.get("provisioned_at_ms") != activated_at_ms
            ):
                raise ProvisioningError("Invitation changed before activation")
            transaction.update(identity, {"status": "active", "activated_at_ms": activated_at_ms})
            transaction.create(
                event,
                {
                    "schema_version": 1,
                    "uid": uid,
                    "actor_uid": actor_uid,
                    "action": "initial_password_identity_activated",
                    "created_at_ms": activated_at_ms,
                },
            )

        write(self.client.transaction())
