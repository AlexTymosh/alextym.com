"""Fleet demo messages, recipient policy, and mail-provider orchestration.

Framework-neutral use case: translate MessageDeliveryError to HTTP in api.vor.
Do not mistake accepted provider delivery for a transactional event write.
"""

from __future__ import annotations

import os
from typing import Literal
from urllib.parse import urlsplit

import httpx

from fleet_hub.services import vor_store

_EMAIL_LOCAL_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'*+-/=?^_`{|}~."
)


class MessageDeliveryError(Exception):
    """A known Fleet message failure, without an HTTP/FastAPI dependency."""

    def __init__(self, reason: str, detail: str | None = None) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(detail or reason)


def valid_email(email: str) -> bool:
    """Validate common ASCII mailbox addresses in linear time (no regex backtracking)."""
    if not 3 <= len(email) <= 254 or not email.isascii() or email.count("@") != 1:
        return False

    local, domain = email.split("@", 1)
    if not 1 <= len(local) <= 64 or any(char not in _EMAIL_LOCAL_CHARS for char in local):
        return False
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False

    labels = domain.split(".")
    if len(labels) < 2:
        return False
    return all(
        1 <= len(label) <= 63
        and label[0].isascii()
        and label[0].isalnum()
        and label[-1].isascii()
        and label[-1].isalnum()
        and all(char.isascii() and (char.isalnum() or char == "-") for char in label)
        for label in labels
    )


def _send_live_email(
    *, recipients: list[str], registration: str, ticket_id: str | None, subject: str
) -> None:
    """Enforce server-derived recipient policy, reserve quota, then call Resend.

    Historical ordering is preserved for this extraction. A provider acceptance
    followed by failure of the later event write is not reconciled here.
    """
    allowed = {
        x.strip().lower()
        for x in os.getenv("VOR_DEMO_ALLOWED_RECIPIENTS", "").split(",")
        if x.strip()
    }
    domains = {
        x.strip().lower().lstrip("@")
        for x in os.getenv("VOR_DEMO_ALLOWED_EMAIL_DOMAINS", "").split(",")
        if x.strip()
    }
    if not allowed and not domains:
        raise MessageDeliveryError("policy_missing")

    # '*' is an explicit opt-in; recipients always come from subscriptions.
    any_domain = "*" in domains
    unapproved = [
        email
        for email in recipients
        if not (any_domain or email in allowed or email.rsplit("@", 1)[-1] in domains)
    ]
    if unapproved:
        raise MessageDeliveryError("recipient_not_allowed")

    limit = max(1, min(int(os.getenv("VOR_DEMO_EMAIL_LIMIT", "15")), 30))
    token = os.getenv("RESEND_API_KEY", "")
    from_email = os.getenv("VOR_DEMO_FROM_EMAIL", "") or os.getenv("CONTACT_FROM_EMAIL", "")
    public_url = os.getenv("VOR_DEMO_PUBLIC_URL", "").strip()
    if not token or not from_email or not public_url.startswith("https://"):
        raise MessageDeliveryError("mail_config_missing")
    host = urlsplit(public_url).hostname or ""
    if host in {"localhost", "127.0.0.1"}:
        raise MessageDeliveryError("public_url_unreachable")

    notification = (
        "This is a test demonstration of the Fleet VOR management system.\n\n"
        f"A new update has been posted for vehicle {registration}"
        + (f" (ticket {ticket_id})" if ticket_id else "")
        + ".\n\nOpen Fleet VOR Hub to read the update:\n"
        + public_url
        + "\n\nThis is a demonstration notification; no operational action is required. "
        "Please do not reply to this email."
    )
    payload: dict = {
        "from": from_email,
        "to": [recipients[0]],
        "subject": subject,
        "text": notification,
    }
    if len(recipients) > 1:
        payload["bcc"] = recipients[1:]

    try:
        reservation_id = vor_store.reserve_email_delivery(len(recipients), limit)
    except ValueError:
        raise MessageDeliveryError("daily_quota_exceeded") from None
    try:
        result = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=12,
        )
        result.raise_for_status()
    except httpx.HTTPError:
        vor_store.finish_email_delivery(reservation_id, "failed_or_unknown")
        raise MessageDeliveryError("provider_unavailable") from None
    vor_store.finish_email_delivery(reservation_id, "accepted")


def post_message(
    *,
    vehicle_id: int,
    ticket_id: str | None,
    kind: Literal["internal", "email"],
    text: str,
    subject: str | None,
) -> dict:
    """Validate, optionally deliver, and record one Fleet message.

    Provider delivery precedes event persistence for compatibility. This
    step intentionally does not add an idempotency key or modify quota states.
    """
    recipients: list[str] = []
    direction = None
    try:
        registration = vor_store.validate_vehicle_ticket(vehicle_id, ticket_id)
    except ValueError as exc:
        raise MessageDeliveryError("invalid_record", str(exc)) from exc

    if kind == "email":
        recipients = vor_store.subscriber_emails(vehicle_id)
        if not recipients:
            raise MessageDeliveryError("no_subscribers")
        if any(not valid_email(email) for email in recipients):
            raise MessageDeliveryError("invalid_subscriber_email")
        prefix = f"[{registration}]" + (f"[{ticket_id}]" if ticket_id else "")
        subject = f"{prefix} {subject or 'Fleet update'}"
        real = os.getenv("VOR_DEMO_SEND_REAL_EMAIL", "false").lower() == "true"
        if real:
            _send_live_email(
                recipients=recipients,
                registration=registration,
                ticket_id=ticket_id,
                subject=subject,
            )
            direction = "outgoing"
        else:
            direction = "simulated_outgoing"

    try:
        event_id = vor_store.add_event(
            vehicle_id,
            ticket_id,
            kind,
            text,
            "Alex",  # Existing demo event actor; preserve persisted behavior.
            subject=subject,
            recipient=",".join(recipients) if kind == "email" else None,
            direction=direction,
        )
    except ValueError as exc:
        raise MessageDeliveryError("invalid_record", str(exc)) from exc

    return {
        "id": event_id,
        "delivery": direction or "internal",
        "recipient_count": len(recipients),
        "recipients": recipients,
    }
