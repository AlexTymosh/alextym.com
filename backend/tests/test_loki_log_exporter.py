import json
import logging
import time
from collections.abc import Mapping

import structlog

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.loki import (
    LokiConfig,
    LokiLogExporter,
    build_loki_payload,
    configure_loki_exporter,
    get_active_loki_exporter,
    shutdown_loki_exporter,
)


def test_configured_structlog_warning_is_exported_to_loki(
    monkeypatch,
    capsys,
) -> None:
    sent_payloads: list[bytes] = []

    def fake_transport(
        _url: str,
        payload: bytes,
        _headers: Mapping[str, str],
        _timeout: float,
    ) -> None:
        sent_payloads.append(payload)

    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_EXPORT_ENABLED", "true")
    monkeypatch.setenv("LOG_EXPORT_MIN_LEVEL", "WARNING")
    monkeypatch.setenv("LOKI_PUSH_URL", "https://logs.example/loki/api/v1/push")
    monkeypatch.setenv("LOKI_USERNAME", "123456")
    monkeypatch.setenv("LOKI_TOKEN", "test-token")
    monkeypatch.setattr("app.core.loki._send_loki_payload", fake_transport)
    get_settings.cache_clear()

    configure_logging(get_settings())
    structlog.get_logger("test").warning(
        "test.warning",
        message="Safe warning.",
        request_id="req_1234567890",
    )
    shutdown_loki_exporter(timeout_seconds=1.0)
    output = capsys.readouterr().out
    logging.getLogger().handlers.clear()

    assert '"event": "test.warning"' in output
    payload = _single_payload(sent_payloads)
    log_line = json.loads(payload["streams"][0]["values"][0][1])
    assert log_line["event"] == "test.warning"
    assert log_line["request_id"] == "req_1234567890"


def test_loki_exporter_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.delenv("LOG_EXPORT_ENABLED", raising=False)
    get_settings.cache_clear()

    exporter = configure_loki_exporter(get_settings())

    assert exporter is None
    assert get_active_loki_exporter() is None


def test_loki_exporter_requires_complete_cloud_settings(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_EXPORT_ENABLED", "true")
    monkeypatch.setenv("LOKI_PUSH_URL", "https://logs.example/loki/api/v1/push")
    monkeypatch.setenv("LOKI_USERNAME", "123456")
    monkeypatch.delenv("LOKI_TOKEN", raising=False)
    get_settings.cache_clear()

    exporter = configure_loki_exporter(get_settings())

    assert exporter is None
    assert get_active_loki_exporter() is None


def test_loki_exporter_sends_warning_payload_with_safe_fields() -> None:
    sent_payloads: list[bytes] = []
    exporter = _build_exporter(
        lambda _url, payload, _headers, _timeout: sent_payloads.append(payload)
    )

    exporter.start()
    accepted = exporter.handle_event(
        {
            "timestamp": "2026-06-07T12:00:00Z",
            "level": "WARNING",
            "service": "portfolio-backend",
            "service_version": "0.1.0",
            "environment": "test",
            "event": "chat.request.failed",
            "message": "Chat request failed.",
            "request_id": "req_1234567890",
            "route": "/api/chat",
            "method": "POST",
            "status_code": 500,
            "error_type": "ProviderRequestError",
        }
    )
    exporter.close(timeout_seconds=1.0)

    assert accepted is True
    payload = _single_payload(sent_payloads)
    stream = payload["streams"][0]
    log_line = json.loads(stream["values"][0][1])

    assert stream["stream"] == {
        "environment": "test",
        "level": "WARNING",
        "service": "portfolio-backend",
    }
    assert log_line["event"] == "chat.request.failed"
    assert log_line["request_id"] == "req_1234567890"
    assert log_line["route"] == "/api/chat"
    assert "Authorization" not in json.dumps(payload)


def test_loki_exporter_drops_info_below_warning() -> None:
    sent_payloads: list[bytes] = []
    exporter = _build_exporter(
        lambda _url, payload, _headers, _timeout: sent_payloads.append(payload)
    )

    exporter.start()
    accepted = exporter.handle_event(
        {
            "level": "INFO",
            "service": "portfolio-backend",
            "environment": "test",
            "event": "http.request.completed",
        }
    )
    exporter.close(timeout_seconds=1.0)

    assert accepted is False
    assert sent_payloads == []


def test_loki_payload_uses_allowlist_and_does_not_leak_sensitive_fields() -> None:
    record = _build_record(
        {
            "level": "ERROR",
            "service": "portfolio-backend",
            "environment": "test",
            "event": "contact.failed",
            "message": "Contact failed for john@example.com",
            "request_id": "req_abcdef123456",
            "email": "john@example.com",
            "authorization": "Bearer secret-token",
            "user_message": "private chat text",
            "token": "secret-token",
        }
    )

    payload_text = build_loki_payload([record]).decode("utf-8")
    payload = json.loads(payload_text)
    log_line = json.loads(payload["streams"][0]["values"][0][1])

    assert log_line["message"] == "[redacted]"
    assert log_line["request_id"] == "req_abcdef123456"
    assert "john@example.com" not in payload_text
    assert "secret-token" not in payload_text
    assert "private chat text" not in payload_text
    assert "request_id" not in payload["streams"][0]["stream"]


def test_loki_exporter_drops_when_queue_is_full() -> None:
    exporter = _build_exporter(lambda *_args: None, queue_max_size=1)

    first_accepted = exporter.handle_event(_warning_event("first.warning"))
    second_accepted = exporter.handle_event(_warning_event("second.warning"))

    assert first_accepted is True
    assert second_accepted is False
    assert exporter.dropped_count == 1


def test_slow_loki_transport_does_not_block_enqueue_path() -> None:
    def slow_transport(
        _url: str,
        _payload: bytes,
        _headers: Mapping[str, str],
        _timeout: float,
    ) -> None:
        time.sleep(0.2)

    exporter = _build_exporter(slow_transport, batch_size=1)
    exporter.start()

    start_time = time.perf_counter()
    for index in range(10):
        exporter.handle_event(_warning_event(f"slow.warning.{index}"))
    elapsed_seconds = time.perf_counter() - start_time
    exporter.close(timeout_seconds=0.1)

    assert elapsed_seconds < 0.05


def test_loki_transport_error_does_not_raise() -> None:
    def failing_transport(*_args) -> None:
        raise OSError("Loki is unavailable")

    exporter = _build_exporter(failing_transport)
    exporter.start()
    accepted = exporter.handle_event(_warning_event("loki.failure"))
    exporter.close(timeout_seconds=1.0)

    assert accepted is True
    assert exporter.transport_error_count == 1


def test_shutdown_loki_exporter_clears_active_exporter(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("LOG_EXPORT_ENABLED", "true")
    monkeypatch.setenv("LOKI_PUSH_URL", "https://logs.example/loki/api/v1/push")
    monkeypatch.setenv("LOKI_USERNAME", "123456")
    monkeypatch.setenv("LOKI_TOKEN", "test-token")
    get_settings.cache_clear()

    exporter = configure_loki_exporter(get_settings())
    assert exporter is not None
    assert get_active_loki_exporter() is exporter

    shutdown_loki_exporter(timeout_seconds=0.1)

    assert get_active_loki_exporter() is None


def _build_exporter(
    transport,
    *,
    queue_max_size: int = 100,
    batch_size: int = 50,
) -> LokiLogExporter:
    return LokiLogExporter(
        LokiConfig(
            push_url="https://logs.example/loki/api/v1/push",
            username="123456",
            token="test-token",
            min_level="WARNING",
            queue_max_size=queue_max_size,
            timeout_seconds=0.1,
            batch_size=batch_size,
            flush_interval_seconds=0.01,
        ),
        transport=transport,
    )


def _single_payload(sent_payloads: list[bytes]) -> dict:
    assert len(sent_payloads) == 1
    return json.loads(sent_payloads[0])


def _warning_event(event_name: str) -> dict[str, str]:
    return {
        "level": "WARNING",
        "service": "portfolio-backend",
        "environment": "test",
        "event": event_name,
    }


def _build_record(event: dict) -> object:
    exporter = _build_exporter(lambda *_args: None)
    exporter.handle_event(event)
    return exporter._queue.get_nowait()
