"""Pure, fail-closed Portfolio Lab identity admission policy.

Admission is distinct from project-level authorization. This policy never
supplies a project grant. Its JSON fixtures are shared with the Next.js policy.
"""

from __future__ import annotations

from typing import Any

OAUTH_PROVIDERS = frozenset({"google.com", "github.com", "microsoft.com"})


def sign_in_provider(claims: dict[str, Any]) -> str:
    firebase = claims.get("firebase")
    if not isinstance(firebase, dict):
        return ""
    provider = firebase.get("sign_in_provider")
    return provider if isinstance(provider, str) else ""


def oauth_subject(claims: dict[str, Any], provider: str) -> str | None:
    firebase = claims.get("firebase")
    identities = firebase.get("identities") if isinstance(firebase, dict) else None
    subjects = identities.get(provider) if isinstance(identities, dict) else None
    if isinstance(subjects, list) and len(subjects) == 1:
        subject = subjects[0]
        if isinstance(subject, str) and subject:
            return subject
    return None


def _valid_timestamp(value: Any) -> bool:
    return type(value) is int and 0 < value < 8_640_000_000_000_000


def admission_decision(
    uid: str,
    owner_uid: str,
    provider: str,
    record: dict[str, Any] | None,
    now_ms: int,
    auth_time: int | None = None,
    subject: str | None = None,
) -> str:
    """Return 'allowed', 'password_expired', or 'denied'; never trust email claims."""
    if not isinstance(uid, str) or not uid or not owner_uid:
        return "denied"
    if provider == "password" and uid == owner_uid:
        return "allowed"
    if provider != "password" and provider not in OAUTH_PROVIDERS:
        return "denied"
    if not isinstance(record, dict):
        return "denied"
    if (
        type(record.get("schema_version")) is not int
        or record["schema_version"] != 1
        or record.get("uid") != uid
        or record.get("status") != "active"
    ):
        return "denied"
    for field in ("password_changed_at_ms", "password_reset_repaired_at_ms"):
        if field in record and (
            not _valid_timestamp(record[field])
            or type(auth_time) is not int
            or auth_time <= record[field] // 1000
        ):
            return "denied"
    password_state = record.get("password_state")
    if provider != "password":
        bindings = record.get("oauth_provider_subjects")
        if not isinstance(bindings, dict) or not subject or bindings.get(provider) != subject:
            return "denied"
        return (
            "allowed"
            if password_state in ("initial", "user_set", "none", "reset_pending")
            else "denied"
        )
    if password_state == "user_set":
        return "allowed"
    if password_state != "initial":
        return "denied"
    expiry_ms = record.get("initial_password_expires_at_ms")
    if not _valid_timestamp(expiry_ms):
        return "denied"
    return "password_expired" if now_ms >= expiry_ms else "allowed"
