import json

import pytest

from app.services import telegram as telegram_module
from app.services.telegram import (
    TELEGRAM_SEND_DOCUMENT_URL,
    TELEGRAM_SEND_MESSAGE_URL,
    TelegramBotClient,
)


@pytest.mark.anyio
async def test_send_message_uses_send_message_for_short_text(monkeypatch) -> None:
    fake_urlopen = FakeUrlopen()
    monkeypatch.setattr(telegram_module, "urlopen", fake_urlopen)

    client = TelegramBotClient(bot_token="token", chat_id="123")

    await client.send_message("Hello")

    assert len(fake_urlopen.requests) == 1
    request = fake_urlopen.requests[0].request
    assert request.full_url == TELEGRAM_SEND_MESSAGE_URL.format(token="token")

    payload = json.loads(request.data.decode("utf-8"))
    assert payload == {
        "chat_id": "123",
        "text": "Hello",
        "disable_web_page_preview": True,
    }


@pytest.mark.anyio
async def test_long_message_is_sent_as_document(monkeypatch) -> None:
    fake_urlopen = FakeUrlopen()
    monkeypatch.setattr(telegram_module, "urlopen", fake_urlopen)

    handoff_id = "hnd_" + "a" * 32
    text = f"Handoff ID: {handoff_id}\n" + "x" * 5000
    client = TelegramBotClient(bot_token="token", chat_id="123")

    await client.send_message(text)

    assert len(fake_urlopen.requests) == 1
    request = fake_urlopen.requests[0].request
    assert request.full_url == TELEGRAM_SEND_DOCUMENT_URL.format(token="token")

    body = request.data
    assert b'name="chat_id"' in body
    assert b"123" in body
    assert b'name="document"' in body
    assert f'filename="handoff-transcript-{handoff_id}.txt"'.encode() in body
    assert text.encode("utf-8") in body


@pytest.mark.anyio
async def test_text_document_uses_explicit_filename(monkeypatch) -> None:
    fake_urlopen = FakeUrlopen()
    monkeypatch.setattr(telegram_module, "urlopen", fake_urlopen)

    client = TelegramBotClient(bot_token="token", chat_id="123")

    await client.send_text_document(
        "Transcript content",
        filename="custom-transcript.txt",
    )

    request = fake_urlopen.requests[0].request
    assert request.full_url == TELEGRAM_SEND_DOCUMENT_URL.format(token="token")
    assert b'filename="custom-transcript.txt"' in request.data
    assert b"Transcript content" in request.data


@pytest.mark.anyio
async def test_long_message_without_handoff_id_uses_generic_filename(
    monkeypatch,
) -> None:
    fake_urlopen = FakeUrlopen()
    monkeypatch.setattr(telegram_module, "urlopen", fake_urlopen)

    client = TelegramBotClient(bot_token="token", chat_id="123")

    await client.send_message("x" * 5000)

    request = fake_urlopen.requests[0].request
    assert b'filename="telegram-message.txt"' in request.data


class FakeUrlopen:
    def __init__(self) -> None:
        self.requests: list[CapturedRequest] = []

    def __call__(self, request, timeout: float) -> "FakeResponse":
        self.requests.append(CapturedRequest(request=request, timeout=timeout))
        return FakeResponse()


class CapturedRequest:
    def __init__(self, *, request, timeout: float) -> None:
        self.request = request
        self.timeout = timeout


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return b'{"ok": true}'
