"""Owner-initiated password setup links without email side effects or grants.

A new user is enabled only with an unguessable, undisclosed bootstrap password;
Firestore remains 'invited' until a trusted reset-code redemption completes.
A partial failure never grants application access and can be retried by UID.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from uuid import uuid4
from typing import Any, Protocol
from urllib.parse import parse_qs, quote, urlsplit

from app.security.lab_provisioning import (
    ProvisioningError,
    normalize_invitee_email,
)

CODE_RE = re.compile(r"[A-Za-z0-9._~-]{10,4096}\Z")


class SetupStore(Protocol):
    def create_invited(self, uid: str, record: dict[str, Any], actor_uid: str) -> None: ...


@dataclass(frozen=True)
class SetupIdentity:
    uid: str
    created: bool


def build_private_action_link(
    provider_link: str, origin: str, *, allow_http_local: bool = False
) -> str:
    """Move the Firebase OOB code to a URL fragment, never a server URL query.

    A fragment is handled by browser JavaScript and is not sent in HTTP request
    targets, access logs or ordinary Referer headers. The code is never stored.
    """
    parsed_origin = urlsplit(origin)
    if (
        not parsed_origin.hostname
        or parsed_origin.username
        or parsed_origin.password
        or parsed_origin.path not in ("", "/")
        or parsed_origin.query
        or parsed_origin.fragment
        or (
            parsed_origin.scheme != "https"
            and not (
                allow_http_local
                and parsed_origin.scheme == "http"
                and parsed_origin.hostname in {"localhost", "127.0.0.1"}
            )
        )
    ):
        raise ValueError("Provide a trusted HTTPS site origin (localhost only in development)")
    parsed_link = urlsplit(provider_link)
    if parsed_link.scheme != "https" or not parsed_link.hostname:
        raise ProvisioningError("Firebase did not return a valid action link")
    query = parse_qs(parsed_link.query)
    code = query.get("oobCode", [""])
    mode = query.get("mode", [""])
    if (
        len(code) != 1
        or len(mode) != 1
        or mode[0] != "resetPassword"
        or not CODE_RE.fullmatch(code[0])
    ):
        raise ProvisioningError("Firebase did not return a valid password reset action code")
    return f"{origin.rstrip('/')}/lab/password/reset#oobCode={quote(code[0], safe='')}"


def create_setup_identity(
    *,
    auth_client: Any,
    identity_store: SetupStore,
    actor_uid: str,
    email: str,
    now_ms: int,
) -> SetupIdentity:
    """Provision a new UID; never auto-attach an existing Firebase email.

    If enabling or Firestore fails, the record stays 'invited' or absent. No
    automatic deletion occurs after a durable invited record was committed.
    """
    normalized = normalize_invitee_email(email)
    if not actor_uid or "/" in actor_uid or type(now_ms) is not int or now_ms <= 0:
        raise ValueError("A trusted Owner UID and timestamp are required")
    try:
        user = auth_client.create_user(
            email=normalized,
            password=secrets.token_urlsafe(48),
            disabled=True,
        )
    except Exception as exc:
        raise ProvisioningError(
            "New account could not be created; existing accounts are never adopted"
        ) from exc
    uid = getattr(user, "uid", "")
    if not isinstance(uid, str) or not uid or "/" in uid:
        raise ProvisioningError("Invalid Firebase UID; inspect disabled accounts")
    try:
        identity_store.create_invited(
            uid,
            {
                "schema_version": 1,
                "uid": uid,
                "status": "invited",
                "password_state": "none",
                "provisioned_at_ms": now_ms,
                "provisioned_by_uid": actor_uid,
            },
            actor_uid,
        )
    except Exception as exc:
        # A disabled Auth user cannot sign in; an ambiguous Firestore result
        # must be repaired explicitly rather than automatically re-bound.
        raise ProvisioningError("Invited state was not confirmed; inspect disabled UID") from exc
    try:
        auth_client.update_user(uid, disabled=False)
    except Exception as exc:
        raise ProvisioningError("Firebase enable was not confirmed; inspect invited UID") from exc
    return SetupIdentity(uid=uid, created=True)


def verify_existing_setup_identity(*, auth_user: Any, record: Any, owner_uid: str) -> str:
    """Only known, non-disabled UIDs can receive a generated recovery link."""
    uid = getattr(auth_user, "uid", None)
    if (
        not isinstance(uid, str)
        or not uid
        or "/" in uid
        or uid == owner_uid
        or bool(getattr(auth_user, "disabled", True))
        or not isinstance(record, dict)
        or type(record.get("schema_version")) is not int
        or record.get("schema_version") != 1
        or record.get("uid") != uid
        or record.get("status") not in {"invited", "active"}
        or record.get("password_state") not in {"initial", "user_set", "none"}
    ):
        raise ProvisioningError("UID is not eligible for a password setup link")
    return uid


class FirestoreSetupIdentityStore:
    """Write invited setup identity and exact-action audit atomically."""

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
                "action": "password_setup_identity_invited",
                "created_at_ms": record["provisioned_at_ms"],
            },
        )
        batch.commit()
