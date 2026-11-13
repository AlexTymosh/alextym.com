"""Pure, fail-closed Portfolio Lab identity admission policy.

Admission is distinct from project-level authorization. This policy never
supplies a project grant. Its JSON fixtures are shared with the Next.js policy.
"""

from __future__ import annotations

from typing import Any

SUPPORTED_PROVIDERS = frozenset({"password", "google.com", "github.com", "microsoft.com"})


def sign_in_provider(claims: dict[str, Any]) -> str:
    firebase = claims.get("firebase")
    if not isinstance(firebase, dict):
        return ""
    provider = firebase.get("sign_in_provider")
    return provider if isinstance(provider, str) else ""


def admission_decision(
    uid: str,
    owner_uid: str,
    provider: str,
    record: dict[str, Any] | None,
    now_ms: int,
) -> str:
    """Return 'allowed', 'password_expired', or 'denied'; never trust email claims."""
    if not isinstance(uid, str) or not uid or not owner_uid:
        return "denied"
    if uid == owner_uid:
        return "allowed"
    if provider not in SUPPORTED_PROVIDERS:
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
    password_state = record.get("password_state")
    if password_state not in {"initial", "user_set", "none"}:
        return "denied"
    if provider != "password":
        return "allowed"
    if password_state == "user_set":
        return "allowed"
    if password_state == "none":
        return "denied"
    expiry_ms = record.get("initial_password_expires_at_ms")
    if type(expiry_ms) is not int or expiry_ms <= 0 or not (0 < expiry_ms < 8_640_000_000_000_000):
        return "denied"
    return "password_expired" if now_ms >= expiry_ms else "allowed"
