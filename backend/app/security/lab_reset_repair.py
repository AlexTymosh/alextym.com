"""Audited, fail-closed repair of interrupted Portfolio Lab password resets.

A pending password reset is not resolved by guessing whether Firebase accepted
an action code. Owner may only return the credential to `none` (no password
admission); the person must receive and redeem another setup link.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.security.lab_provisioning import ProvisioningError


class ResetRepairAuth(Protocol):
    def get_user(self, uid: str) -> Any: ...

    def revoke_refresh_tokens(self, uid: str) -> None: ...


class ResetRepairStore(Protocol):
    def load(self, uid: str) -> dict | None: ...

    def mark_password_unavailable(self, uid: str, actor_uid: str, now_ms: int) -> None: ...


def is_repairable_pending_reset(uid: str, owner_uid: str, record: Any) -> bool:
    return (
        isinstance(uid, str)
        and bool(uid)
        and "/" not in uid
        and isinstance(owner_uid, str)
        and bool(owner_uid)
        and uid != owner_uid
        and isinstance(record, dict)
        and type(record.get("schema_version")) is int
        and record["schema_version"] == 1
        and record.get("uid") == uid
        and record.get("status") in {"active", "invited"}
        and record.get("password_state") == "reset_pending"
    )


def repair_interrupted_reset(
    *,
    auth_client: ResetRepairAuth,
    identity_store: ResetRepairStore,
    owner_uid: str,
    uid: str,
    now_ms: int,
) -> None:
    """Revoke first, then atomically deny password access and audit repair.

    Network errors deliberately propagate as a sanitized operator failure.
    Never reenable a revoked identity, create a grant, or set `user_set`.
    """
    if type(now_ms) is not int or not 0 < now_ms < 8_640_000_000_000_000:
        raise ValueError("Invalid trusted timestamp")
    try:
        if not is_repairable_pending_reset(uid, owner_uid, identity_store.load(uid)):
            raise ProvisioningError("Only a pending non-Owner identity can be repaired")
        user = auth_client.get_user(uid)
        if user.disabled or user.uid != uid:
            raise ProvisioningError("Firebase user must exist and be enabled")
        auth_client.revoke_refresh_tokens(uid)
        identity_store.mark_password_unavailable(uid, owner_uid, now_ms)
    except ProvisioningError:
        raise
    except Exception as exc:
        raise ProvisioningError("Reset repair not confirmed; inspect UID and retry safely") from exc


class FirestoreResetRepairStore:
    """Recheck pending status inside a transaction to avoid entitlement races."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def _identity(self, uid: str):
        return self.client.collection("portfolio_lab_identities").document(uid)

    def load(self, uid: str) -> dict | None:
        snapshot = self._identity(uid).get(timeout=5.0)
        return snapshot.to_dict() if snapshot.exists else None

    def mark_password_unavailable(self, uid: str, actor_uid: str, now_ms: int) -> None:
        from google.cloud import firestore as google_firestore

        identity = self._identity(uid)
        event = self.client.collection("portfolio_lab_invitation_events").document()

        @google_firestore.transactional
        def write(transaction):
            snapshot = identity.get(transaction=transaction)
            if not is_repairable_pending_reset(
                uid, actor_uid, snapshot.to_dict() if snapshot.exists else None
            ):
                raise ProvisioningError("Pending reset changed; no repair was applied")
            transaction.update(
                identity,
                {
                    "password_state": "none",
                    "password_reset_started_at_ms": google_firestore.DELETE_FIELD,
                    "password_reset_repaired_at_ms": now_ms,
                },
            )
            transaction.create(
                event,
                {
                    "schema_version": 1,
                    "uid": uid,
                    "actor_uid": actor_uid,
                    "action": "password_reset_repaired_requires_new_link",
                    "created_at_ms": now_ms,
                },
            )

        write(self.client.transaction())
