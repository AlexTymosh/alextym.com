import json
import re
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from starlette.concurrency import run_in_threadpool

TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_SEND_DOCUMENT_URL = "https://api.telegram.org/bot{token}/sendDocument"
TELEGRAM_MESSAGE_MAX_CHARS = 4096
TELEGRAM_TEXT_DOCUMENT_FILENAME = "telegram-message.txt"
HANDOFF_ID_PATTERN = re.compile(r"\b(hnd_[a-f0-9]{32})\b", re.IGNORECASE)


class TelegramDeliveryError(Exception):
    pass


class TelegramBotClient:
    def __init__(
        self,
        *,
        bot_token: str,
        chat_id: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout_seconds = timeout_seconds

    async def send_message(self, text: str) -> None:
        if len(text) <= TELEGRAM_MESSAGE_MAX_CHARS:
            await run_in_threadpool(self._send_message_sync, text)
            return

        await self.send_text_document(
            text,
            filename=_document_filename_from_text(text),
        )

    async def send_text_document(self, text: str, *, filename: str) -> None:
        await run_in_threadpool(
            self._send_text_document_sync,
            text,
            filename,
        )

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
        self._execute_request(request)

    def _send_text_document_sync(self, text: str, filename: str) -> None:
        document_bytes = text.encode("utf-8")
        body, content_type = _build_multipart_form_data(
            fields={
                "chat_id": self._chat_id,
                "disable_content_type_detection": "true",
            },
            files={
                "document": (
                    _safe_document_filename(filename),
                    document_bytes,
                    "text/plain; charset=utf-8",
                ),
            },
        )
        request = Request(
            TELEGRAM_SEND_DOCUMENT_URL.format(token=self._bot_token),
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        self._execute_request(request)

    def _execute_request(self, request: Request) -> None:
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


def _build_multipart_form_data(
    *,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----alextym-telegram-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                _content_disposition(name).encode("utf-8"),
                b"\r\n",
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    for name, (filename, content, content_type) in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                _content_disposition(name, filename).encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                content,
                b"\r\n",
            ]
        )

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _content_disposition(name: str, filename: str | None = None) -> str:
    disposition = f'Content-Disposition: form-data; name="{name}"'
    if filename is not None:
        disposition += f'; filename="{filename}"'
    return disposition + "\r\n"


def _safe_document_filename(filename: str) -> str:
    safe_name = filename.replace("\\", "-").replace("/", "-").replace('"', "")
    safe_name = safe_name.strip()
    if not safe_name:
        return TELEGRAM_TEXT_DOCUMENT_FILENAME
    if not safe_name.lower().endswith(".txt"):
        return f"{safe_name}.txt"
    return safe_name


def _document_filename_from_text(text: str) -> str:
    match = HANDOFF_ID_PATTERN.search(text)
    if match:
        return f"handoff-transcript-{match.group(1).lower()}.txt"
    return TELEGRAM_TEXT_DOCUMENT_FILENAME


def _is_successful_telegram_response(response: Any) -> bool:
    return isinstance(response, dict) and response.get("ok") is True
