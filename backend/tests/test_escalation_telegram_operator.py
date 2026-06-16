from typing import Any

import pytest

from app.schemas.escalation import EscalationRequest
from app.services.escalation import TelegramEscalationNotifier

TEST_HANDOFF_ID = "hnd_" + "a" * 32


@pytest.mark.anyio
async def test_handoff_notification_sends_control_message_first() -> None:
    telegram_client = FakeTelegramClient()
    notifier = TelegramEscalationNotifier(telegram_client=telegram_client)

    await notifier.notify(_escalation_request(), handoff_id=TEST_HANDOFF_ID)

    assert telegram_client.calls[0]["type"] == "message"
    assert telegram_client.calls[0]["parse_mode"] == "HTML"
    assert "<b>🚨 New handoff request — alextym.com</b>" in telegram_client.calls[0]["text"]
    assert f"<code>Ref: {TEST_HANDOFF_ID}</code>" in telegram_client.calls[0]["text"]
    assert "<b>Button actions</b>" not in telegram_client.calls[0]["text"]
    assert (
        "Use the buttons below for quick operator actions."
        not in (telegram_client.calls[0]["text"])
    )
    assert (
        "The full transcript is attached as a text file." not in (telegram_client.calls[0]["text"])
    )
    assert "Fallback close command:" not in telegram_client.calls[0]["text"]


@pytest.mark.anyio
async def test_handoff_notification_adds_inline_operator_actions() -> None:
    telegram_client = FakeTelegramClient()
    notifier = TelegramEscalationNotifier(telegram_client=telegram_client)

    await notifier.notify(_escalation_request(), handoff_id=TEST_HANDOFF_ID)

    assert telegram_client.calls[0]["reply_markup"] == {
        "inline_keyboard": [
            [
                {
                    "text": "✍️ Reply manually with custom text",
                    "callback_data": f"handoff:reply:{TEST_HANDOFF_ID}",
                },
                {
                    "text": "✅ Close + notify visitor",
                    "callback_data": f"handoff:close:{TEST_HANDOFF_ID}",
                },
            ],
            [
                {
                    "text": "👋 Send: “Hi, I’m connected now and reading...”",
                    "callback_data": f"handoff:reading:{TEST_HANDOFF_ID}",
                },
            ],
            [
                {
                    "text": "⏳ Send: “Hi, I’m connected, but I’m sorry...”",
                    "callback_data": f"handoff:contact:{TEST_HANDOFF_ID}",
                },
            ],
            [
                {
                    "text": "❓ Send: “Are you still there? I’m ready...”",
                    "callback_data": f"handoff:still:{TEST_HANDOFF_ID}",
                },
            ],
        ]
    }


@pytest.mark.anyio
async def test_handoff_notification_sends_transcript_as_document() -> None:
    telegram_client = FakeTelegramClient()
    notifier = TelegramEscalationNotifier(telegram_client=telegram_client)

    await notifier.notify(_escalation_request(), handoff_id=TEST_HANDOFF_ID)

    assert telegram_client.calls[1] == {
        "type": "document",
        "filename": f"handoff-transcript-{TEST_HANDOFF_ID}.txt",
        "text": telegram_client.calls[1]["text"],
    }
    assert "Handoff transcript from alextym.com" in telegram_client.calls[1]["text"]
    assert "User: Can I speak to the site owner?" in telegram_client.calls[1]["text"]
    assert (
        "Assistant: Would you like me to connect you with the site owner?"
        in telegram_client.calls[1]["text"]
    )


@pytest.mark.anyio
async def test_handoff_control_message_includes_operator_summary() -> None:
    telegram_client = FakeTelegramClient()
    notifier = TelegramEscalationNotifier(telegram_client=telegram_client)

    await notifier.notify(_escalation_request(), handoff_id=TEST_HANDOFF_ID)

    control_message = telegram_client.calls[0]["text"]
    assert "<b>AI messages before handoff:</b> 1" in control_message
    assert "<b>Last user message</b>" in control_message
    assert "<blockquote>Can I speak to the site owner?</blockquote>" in control_message
    assert "Reason:" not in control_message
    assert "Handoff ID:" not in control_message
    assert "State:" not in control_message


@pytest.mark.anyio
async def test_handoff_control_message_escapes_user_text_for_telegram_html() -> None:
    telegram_client = FakeTelegramClient()
    notifier = TelegramEscalationNotifier(telegram_client=telegram_client)

    await notifier.notify(
        _escalation_request(user_message="Can <b>owner</b> read this & reply?"),
        handoff_id=TEST_HANDOFF_ID,
    )

    control_message = telegram_client.calls[0]["text"]
    assert "Can &lt;b&gt;owner&lt;/b&gt; read this &amp; reply?" in control_message
    assert "Can <b>owner</b> read this & reply?" not in control_message


class FakeTelegramClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def send_message(
        self,
        text: str,
        *,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        self.calls.append(
            {
                "type": "message",
                "text": text,
                "parse_mode": parse_mode or "",
                "reply_markup": reply_markup,
            }
        )

    async def send_text_document(self, text: str, *, filename: str) -> None:
        self.calls.append(
            {
                "type": "document",
                "filename": filename,
                "text": text,
            }
        )


def _escalation_request(
    *,
    user_message: str = "Can I speak to the site owner?",
) -> EscalationRequest:
    return EscalationRequest(
        consent_accepted=True,
        reason="user_requested_human",
        transcript=[
            {
                "role": "user",
                "content": user_message,
            },
            {
                "role": "assistant",
                "content": "Would you like me to connect you with the site owner?",
            },
        ],
        company_website="",
    )
