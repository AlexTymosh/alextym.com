from datetime import UTC, datetime
from html import escape
from typing import Any

from app.core.project_config import get_project_config
from app.schemas.escalation import EscalationMessageRequest, EscalationRequest
from app.services.escalation_sessions import (
    ESCALATION_SESSION_STATE_CLOSED,
    ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
)
from app.services.handoff_copy import (
    CONTACT_QUICK_REPLY_BUTTON_LABEL,
    READING_QUICK_REPLY_BUTTON_LABEL,
    STILL_THERE_QUICK_REPLY_BUTTON_LABEL,
)

_PROJECT_CONFIG = get_project_config()
_SITE_DOMAIN = _PROJECT_CONFIG.site.domain


def build_telegram_control_message(
    escalation_request: EscalationRequest,
    *,
    handoff_id: str,
) -> str:
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    created_date, created_time, created_offset = _split_iso_datetime(created_at)
    last_user_message = _last_user_message(escalation_request)
    lines = [
        f"<b>\U0001f6a8 New handoff request \u2014 {_html_escape(_SITE_DOMAIN)}</b>",
        "",
        "<b>Last user message</b>",
        f"<blockquote>{_html_escape(_clip_control_text(last_user_message))}</blockquote>",
        "",
        "<b>Created at</b>",
        f"<code>{_html_escape(created_date)}</code>",
        f"<b>{_html_escape(created_time)}</b> {_html_escape(created_offset)}",
        "",
        f"<b>AI messages before handoff:</b> {_assistant_message_count(escalation_request)}",
        f"<b>Status:</b> {_telegram_status_label(ESCALATION_SESSION_STATE_WAITING_FOR_ALEX)}",
    ]

    if _should_show_handoff_reason(escalation_request.reason):
        lines.extend(
            [
                "",
                f"<b>Reason:</b> <code>{_html_escape(escalation_request.reason)}</code>",
            ]
        )

    lines.extend(
        [
            "",
            f"<code>Ref: {_html_escape(handoff_id)}</code>",
        ]
    )
    return "\n".join(lines)


def build_telegram_handoff_reply_markup(handoff_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "\u270d\ufe0f Reply manually with custom text",
                    "callback_data": f"handoff:reply:{handoff_id}",
                },
                {
                    "text": "\u2705 Close + notify visitor",
                    "callback_data": f"handoff:close:{handoff_id}",
                },
            ],
            [
                {
                    "text": READING_QUICK_REPLY_BUTTON_LABEL,
                    "callback_data": f"handoff:reading:{handoff_id}",
                },
            ],
            [
                {
                    "text": CONTACT_QUICK_REPLY_BUTTON_LABEL,
                    "callback_data": f"handoff:contact:{handoff_id}",
                },
            ],
            [
                {
                    "text": STILL_THERE_QUICK_REPLY_BUTTON_LABEL,
                    "callback_data": f"handoff:still:{handoff_id}",
                },
            ],
        ]
    }


def build_telegram_transcript_message(
    escalation_request: EscalationRequest,
    *,
    handoff_id: str | None,
) -> str:
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    transcript_lines = []
    for item in escalation_request.transcript:
        role = "User" if item.role == "user" else "Assistant"
        transcript_lines.append(f"{role}: {item.content}")

    header_lines = [
        f"Handoff transcript from {_SITE_DOMAIN}",
        f"Created at: {created_at}",
        f"Reason: {escalation_request.reason}",
    ]
    if handoff_id:
        header_lines.append(f"Handoff ID: {handoff_id}")

    return "\n\n".join(
        [
            "\n".join(header_lines),
            "Transcript:\n" + "\n\n".join(transcript_lines),
            "No email or phone number was shared unless the visitor typed it manually.",
        ]
    )


def build_telegram_transcript_filename(handoff_id: str) -> str:
    return f"handoff-transcript-{handoff_id}.txt"


def build_telegram_user_message_notification(
    message_request: EscalationMessageRequest,
    *,
    handoff_id: str,
) -> str:
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    return "\n".join(
        [
            f"\U0001f4ac <b>New visitor message</b> \u2014 {_html_escape(_SITE_DOMAIN)}",
            "",
            "<b>Created at</b>",
            f"<code>{_html_escape(created_at)}</code>",
            "",
            "<b>User message</b>",
            f"<blockquote>{_html_escape(_clip_control_text(message_request.content))}</blockquote>",
            "",
            f"<b>Ref:</b> <code>{_html_escape(handoff_id)}</code>",
            "",
            "Reply to this Telegram message to send your answer back to the website chat.",
        ]
    )


def _split_iso_datetime(value: str) -> tuple[str, str, str]:
    created_date, _, time_with_offset = value.partition("T")
    if "+" in time_with_offset:
        created_time, raw_offset = time_with_offset.split("+", 1)
        return created_date, created_time, f"+{raw_offset}"
    if "-" in time_with_offset[1:]:
        created_time, raw_offset = time_with_offset.rsplit("-", 1)
        return created_date, created_time, f"-{raw_offset}"
    return created_date, time_with_offset, "UTC"


def _assistant_message_count(escalation_request: EscalationRequest) -> int:
    return sum(1 for item in escalation_request.transcript if item.role == "assistant")


def _should_show_handoff_reason(reason: str) -> bool:
    return reason != "user_requested_human"


def _telegram_status_label(state: str) -> str:
    if state == ESCALATION_SESSION_STATE_WAITING_FOR_ALEX:
        return "\U0001f534 Waiting for first operator reply"
    if state == ESCALATION_SESSION_STATE_CLOSED:
        return "\U0001f7e2 Closed"
    return _html_escape(state)


def _last_user_message(escalation_request: EscalationRequest) -> str:
    for item in reversed(escalation_request.transcript):
        if item.role == "user":
            return item.content
    return ""


def _html_escape(text: str) -> str:
    return escape(text or "No user message found.", quote=False)


def _clip_control_text(text: str, max_chars: int = 500) -> str:
    compact_text = " ".join(text.split())
    if len(compact_text) <= max_chars:
        return compact_text
    return compact_text[: max_chars - 1].rstrip() + "\u2026"
