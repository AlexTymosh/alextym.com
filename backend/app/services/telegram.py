import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from starlette.concurrency import run_in_threadpool

TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_MESSAGE_MAX_CHARS = 4096
TELEGRAM_SAFE_MESSAGE_CHARS = 3800


class TelegramDeliveryError(Exception):
    pass


class TelegramBotClient:
    def __init__(self, *, bot_token: str, chat_id: str, timeout_seconds: float = 10.0) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout_seconds = timeout_seconds

    async def send_message(self, text: str) -> None:
        for chunk in _split_telegram_message(text):
            await run_in_threadpool(self._send_message_sync, chunk)

    def _send_message_sync(self, text: str) -> None:
        payload = json.dumps(
            {
                "chat_id": self._chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = Request(
            TELEGRAM_SEND_MESSAGE_URL.format(token=self._bot_token),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise TelegramDeliveryError("Telegram API request failed.") from exc

        try:
            decoded_response = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise TelegramDeliveryError("Telegram API response was not valid JSON.") from exc

        if not _is_successful_telegram_response(decoded_response):
            raise TelegramDeliveryError("Telegram API returned an unsuccessful response.")


def _is_successful_telegram_response(response: Any) -> bool:
    return isinstance(response, dict) and response.get("ok") is True


def _split_telegram_message(text: str) -> list[str]:
    if len(text) <= TELEGRAM_MESSAGE_MAX_CHARS:
        return [text]

    chunks: list[str] = []
    remaining_text = text
    while remaining_text:
        chunks.append(remaining_text[:TELEGRAM_SAFE_MESSAGE_CHARS].rstrip())
        remaining_text = remaining_text[TELEGRAM_SAFE_MESSAGE_CHARS:].lstrip()

    return [chunk for chunk in chunks if chunk]
