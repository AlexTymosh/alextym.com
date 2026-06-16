from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILES = (
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / ".env.local",
    PROJECT_ROOT / "backend" / ".env",
    PROJECT_ROOT / "backend" / ".env.local",
    PROJECT_ROOT / "frontend" / ".env.local",
    PROJECT_ROOT / "frontend" / ".env.development.local",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Forward Telegram getUpdates events to the local backend webhook."
    )
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--webhook-path", default="/api/telegram/webhook")
    args = parser.parse_args()

    load_dotenv_files()

    bot_token = required_env("TELEGRAM_DEV_BOT_TOKEN")
    webhook_secret = required_env("TELEGRAM_WEBHOOK_SECRET")

    backend_origin = f"http://127.0.0.1:{args.backend_port}"
    local_webhook_url = f"{backend_origin}{args.webhook_path}"

    bot_info = telegram_request(bot_token, "getMe", {}, timeout=15)
    username = bot_info.get("result", {}).get("username", "unknown")

    print()
    print("Starting local Telegram polling bridge...")
    print(f"Dev bot: @{username}")
    print(f"Backend webhook: {local_webhook_url}")
    print("Mode: Telegram getUpdates -> local backend webhook")
    print()

    wait_for_backend(backend_origin)

    print("Local backend is ready.")
    print("Disabling webhook for the dev Telegram bot so getUpdates can be used locally...")
    telegram_request(
        bot_token,
        "deleteWebhook",
        {"drop_pending_updates": "true"},
        timeout=15,
    )

    print()
    print("Telegram local polling bridge is ready.")
    print("Open the local website:")
    print("http://127.0.0.1:3000/chat")
    print()
    print("Keep this terminal open. Press Ctrl+C to stop local dev mode.")
    print()

    offset: int | None = None

    while True:
        body: dict[str, str] = {
            "timeout": "25",
            "allowed_updates": '["message","callback_query"]',
        }
        if offset is not None:
            body["offset"] = str(offset)

        try:
            response = telegram_request(bot_token, "getUpdates", body, timeout=35)
        except RuntimeError as exc:
            print(f"WARNING: Could not fetch Telegram updates: {exc}", flush=True)
            time.sleep(3)
            continue

        updates = response.get("result", [])
        if not isinstance(updates, list):
            print(f"WARNING: Telegram getUpdates returned unexpected payload: {response}")
            time.sleep(3)
            continue

        for update in updates:
            if not isinstance(update, dict):
                continue

            update_id = int(update.get("update_id", 0))
            ok = forward_update(local_webhook_url, webhook_secret, update)

            # Do not get stuck on one malformed old update forever.
            if update_id:
                offset = update_id + 1

            if ok:
                if update.get("callback_query"):
                    print(
                        f"Forwarded Telegram callback_query update {update_id} "
                        "to local backend.",
                        flush=True,
                    )
                elif update.get("message"):
                    print(
                        f"Forwarded Telegram message update {update_id} "
                        "to local backend.",
                        flush=True,
                    )
                else:
                    print(f"Forwarded Telegram update {update_id} to local backend.", flush=True)

    return 0


def load_dotenv_files() -> None:
    for env_file in ENV_FILES:
        if not env_file.exists():
            continue

        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line.removeprefix("export ").strip()
            if "=" not in line:
                continue

            name, value = line.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(name, value)


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set.")
    return value


def wait_for_backend(backend_origin: str) -> None:
    warmup_url = f"{backend_origin}/api/warmup"
    for _ in range(60):
        try:
            request_json(warmup_url, timeout=2)
            return
        except RuntimeError:
            time.sleep(1)
    raise RuntimeError(f"Local backend did not become ready at {warmup_url}")


def telegram_request(
    bot_token: str,
    method: str,
    body: dict[str, str],
    *,
    timeout: int,
) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    encoded_body = urllib.parse.urlencode(body).encode("utf-8")

    try:
        payload = request_json(
            url,
            data=encoded_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
    except RuntimeError as exc:
        raise RuntimeError(str(exc)) from exc

    if not payload.get("ok"):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))

    return payload


def forward_update(
    local_webhook_url: str,
    webhook_secret: str,
    update: dict[str, Any],
) -> bool:
    body = json.dumps(update, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    try:
        request_json(
            local_webhook_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Telegram-Bot-Api-Secret-Token": webhook_secret,
            },
            timeout=10,
        )
    except RuntimeError as exc:
        update_id = update.get("update_id", "unknown")
        print(
            f"WARNING: Could not forward Telegram update {update_id} "
            f"to local backend: {exc}",
            flush=True,
        )
        print("Forwarded JSON payload:", flush=True)
        print(json.dumps(update, ensure_ascii=False, indent=2), flush=True)
        return False

    return True


def request_json(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers or {},
        method="POST" if data is not None else "GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc

    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response: {response_body}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(f"Unexpected JSON response: {parsed!r}")

    return parsed


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print()
        print("Telegram local polling bridge stopped.")
        raise SystemExit(0)
    except RuntimeError as exc:
        print()
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
