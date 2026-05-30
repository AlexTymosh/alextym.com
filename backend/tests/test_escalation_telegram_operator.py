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
    assert "New handoff request from alextym.com" in telegram_client.calls[0]["text"]
    assert f"Handoff ID: {TEST_HANDOFF_ID}" in telegram_client.calls[0]["text"]
    assert "Reply to this message" in telegram_client.calls[0]["text"]
    assert "The full transcript is attached as a text file." in (telegram_client.calls[0]["text"])


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
    assert "User: Can I speak to Alex?" in telegram_client.calls[1]["text"]
    assert (
        "Assistant: Would you like me to connect you with Alex?"
        in (telegram_client.calls[1]["text"])
    )


@pytest.mark.anyio
async def test_handoff_control_message_includes_operator_summary() -> None:
    telegram_client = FakeTelegramClient()
    notifier = TelegramEscalationNotifier(telegram_client=telegram_client)

    await notifier.notify(_escalation_request(), handoff_id=TEST_HANDOFF_ID)

    control_message = telegram_client.calls[0]["text"]
    assert "Messages: 2" in control_message
    assert "Last user message:" in control_message
    assert "Can I speak to Alex?" in control_message


class FakeTelegramClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def send_message(self, text: str) -> None:
        self.calls.append({"type": "message", "text": text})

    async def send_text_document(self, text: str, *, filename: str) -> None:
        self.calls.append(
            {
                "type": "document",
                "filename": filename,
                "text": text,
            }
        )


def _escalation_request() -> EscalationRequest:
    return EscalationRequest(
        consent_accepted=True,
        reason="user_requested_human",
        transcript=[
            {
                "role": "user",
                "content": "Can I speak to Alex?",
            },
            {
                "role": "assistant",
                "content": "Would you like me to connect you with Alex?",
            },
        ],
        company_website="",
    )
