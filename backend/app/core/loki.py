from __future__ import annotations

import base64
import json
import queue
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings

LogTransport = Callable[[str, bytes, Mapping[str, str], float], None]

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
SAFE_LOG_FIELDS = {
    "timestamp",
    "level",
    "service",
    "service_version",
    "environment",
    "event",
    "message",
    "request_id",
    "logger",
    "method",
    "route",
    "status_code",
    "status_class",
    "duration_ms",
    "error_type",
}
LOKI_LABEL_FIELDS = ("service", "environment", "level")
SENSITIVE_VALUE_MARKERS = (
    "authorization",
    "bearer ",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "@",
)
MAX_LOG_VALUE_LENGTH = 500

_active_exporter: LokiLogExporter | None = None
_exporter_lock = threading.Lock()


class LokiExporterProtocol(Protocol):
    def handle_event(self, event_dict: Mapping[str, Any]) -> bool:
        pass

    def close(self, *, timeout_seconds: float | None = None) -> None:
        pass


@dataclass(frozen=True)
class LokiConfig:
    push_url: str
    username: str
    token: str
    min_level: str
    queue_max_size: int
    timeout_seconds: float
    batch_size: int
    flush_interval_seconds: float


@dataclass(frozen=True)
class LokiRecord:
    labels: dict[str, str]
    line: dict[str, Any]
    timestamp_ns: str


class LokiLogExporter:
    def __init__(
        self,
        config: LokiConfig,
        *,
        transport: LogTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or _send_loki_payload
        self._queue: queue.Queue[LokiRecord] = queue.Queue(maxsize=config.queue_max_size)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="loki-log-exporter",
            daemon=True,
        )
        self._started = False
        self._dropped_count = 0
        self._transport_error_count = 0

    @property
    def dropped_count(self) -> int:
        return self._dropped_count

    @property
    def transport_error_count(self) -> int:
        return self._transport_error_count

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread.start()

    def handle_event(self, event_dict: Mapping[str, Any]) -> bool:
        if not _is_exportable_level(event_dict, self._config.min_level):
            return False

        record = _build_loki_record(event_dict)
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            self._dropped_count += 1
            return False
        return True

    def close(self, *, timeout_seconds: float | None = None) -> None:
        if not self._started:
            return

        self._stop_event.set()
        timeout = timeout_seconds or max(0.1, self._config.timeout_seconds)
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        while not self._stop_event.is_set() or not self._queue.empty():
            batch = self._collect_batch()
            if not batch:
                continue
            self._send_batch(batch)

    def _collect_batch(self) -> list[LokiRecord]:
        try:
            first_record = self._queue.get(timeout=self._config.flush_interval_seconds)
        except queue.Empty:
            return []

        batch = [first_record]
        while len(batch) < self._config.batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _send_batch(self, batch: Sequence[LokiRecord]) -> None:
        try:
            payload = build_loki_payload(batch)
            headers = _loki_headers(self._config.username, self._config.token)
            self._transport(
                self._config.push_url,
                payload,
                headers,
                self._config.timeout_seconds,
            )
        except Exception:
            self._transport_error_count += 1
        finally:
            for _record in batch:
                self._queue.task_done()


def configure_loki_exporter(settings: Settings) -> LokiLogExporter | None:
    global _active_exporter

    with _exporter_lock:
        shutdown_loki_exporter()

        if not settings.log_export_enabled:
            _active_exporter = None
            return None

        config = _loki_config_from_settings(settings)
        if config is None:
            _active_exporter = None
            _write_internal_warning("Loki log export is enabled but Loki settings are incomplete.")
            return None

        exporter = LokiLogExporter(config)
        exporter.start()
        _active_exporter = exporter
        return exporter


def get_active_loki_exporter() -> LokiLogExporter | None:
    return _active_exporter


def shutdown_loki_exporter(*, timeout_seconds: float | None = None) -> None:
    global _active_exporter

    exporter = _active_exporter
    if exporter is None:
        return

    exporter.close(timeout_seconds=timeout_seconds)
    _active_exporter = None


def loki_processor(exporter: LokiExporterProtocol):
    def processor(
        _logger: Any,
        _method_name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        exporter.handle_event(event_dict)
        return event_dict

    return processor


def build_loki_payload(records: Sequence[LokiRecord]) -> bytes:
    streams_by_labels: dict[tuple[tuple[str, str], ...], list[list[str]]] = {}
    labels_by_key: dict[tuple[tuple[str, str], ...], dict[str, str]] = {}

    for record in records:
        labels_key = tuple(sorted(record.labels.items()))
        labels_by_key[labels_key] = record.labels
        streams_by_labels.setdefault(labels_key, []).append(
            [record.timestamp_ns, json.dumps(record.line, separators=(",", ":"))]
        )

    streams = [
        {"stream": labels_by_key[labels_key], "values": values}
        for labels_key, values in streams_by_labels.items()
    ]
    return json.dumps({"streams": streams}).encode("utf-8")


def _loki_config_from_settings(settings: Settings) -> LokiConfig | None:
    if not settings.loki_push_url or not settings.loki_username:
        return None
    if not settings.loki_token:
        return None

    return LokiConfig(
        push_url=settings.loki_push_url,
        username=settings.loki_username,
        token=settings.loki_token,
        min_level=settings.log_export_min_level,
        queue_max_size=settings.loki_queue_max_size,
        timeout_seconds=settings.loki_timeout_seconds,
        batch_size=settings.loki_batch_size,
        flush_interval_seconds=settings.loki_flush_interval_seconds,
    )


def _build_loki_record(event_dict: Mapping[str, Any]) -> LokiRecord:
    safe_line = _safe_log_line(event_dict)
    labels = _safe_loki_labels(safe_line)
    return LokiRecord(
        labels=labels,
        line=safe_line,
        timestamp_ns=str(time.time_ns()),
    )


def _safe_log_line(event_dict: Mapping[str, Any]) -> dict[str, Any]:
    safe_line: dict[str, Any] = {}
    for key in SAFE_LOG_FIELDS:
        if key not in event_dict:
            continue
        value = _safe_log_value(event_dict[key])
        if value is not None:
            safe_line[key] = value
    return safe_line


def _safe_loki_labels(safe_line: Mapping[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for key in LOKI_LABEL_FIELDS:
        raw_value = safe_line.get(key)
        if isinstance(raw_value, str) and raw_value:
            labels[key] = _safe_label_value(raw_value)

    labels.setdefault("service", "portfolio-backend")
    labels.setdefault("environment", "unknown")
    labels.setdefault("level", "UNKNOWN")
    return labels


def _safe_log_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _safe_string_value(value)
    return str(type(value).__name__)


def _safe_string_value(value: str) -> str:
    if _looks_sensitive_value(value):
        return "[redacted]"
    return value[:MAX_LOG_VALUE_LENGTH]


def _looks_sensitive_value(value: str) -> bool:
    normalized_value = value.casefold()
    return any(marker in normalized_value for marker in SENSITIVE_VALUE_MARKERS)


def _safe_label_value(value: str) -> str:
    allowed_chars = []
    for char in value[:80]:
        if char.isalnum() or char in {"_", "-", "."}:
            allowed_chars.append(char)
        else:
            allowed_chars.append("_")
    return "".join(allowed_chars) or "unknown"


def _is_exportable_level(event_dict: Mapping[str, Any], min_level: str) -> bool:
    level = str(event_dict.get("level", "INFO")).upper()
    level_value = LOG_LEVELS.get(level, LOG_LEVELS["INFO"])
    min_level_value = LOG_LEVELS.get(min_level.upper(), LOG_LEVELS["WARNING"])
    return level_value >= min_level_value


def _loki_headers(username: str, token: str) -> dict[str, str]:
    credentials = f"{username}:{token}".encode("utf-8")
    encoded_credentials = base64.b64encode(credentials).decode("ascii")
    return {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/json",
    }


def _send_loki_payload(
    push_url: str,
    payload: bytes,
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> None:
    request = urllib.request.Request(
        url=push_url,
        data=payload,
        headers=dict(headers),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        if response.status >= 400:
            raise OSError(f"Loki returned status {response.status}")


def _write_internal_warning(message: str) -> None:
    sys.stderr.write(f"{message}\n")
