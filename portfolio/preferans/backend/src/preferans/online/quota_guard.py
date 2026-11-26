"""Process-local quota circuit. No identity, state, credentials or DB operations."""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable


class QuotaUnavailable(RuntimeError):
    """A known quota failure has opened the circuit."""


def is_quota_error(error: BaseException) -> bool:
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, QuotaUnavailable) or type(current).__name__ in {
            "ResourceExhausted",
            "QuotaExceeded",
        }:
            return True
        # Google API exceptions sometimes wrap the gRPC status in a cause.
        code = getattr(current, "grpc_status_code", None)
        if getattr(code, "name", None) == "RESOURCE_EXHAUSTED":
            return True
        wrapped = getattr(current, "cause", None)
        current = current.__cause__ or (
            wrapped
            if isinstance(wrapped, BaseException)
            else None
            if current.__suppress_context__
            else current.__context__
        )
    return False


class QuotaCircuit:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._until = 0.0
        self._last_failure: float | None = None
        self._streak = 0
        self._trips = 0
        self._blocked = 0

    def retry_after(self) -> int:
        with self._lock:
            return max(0, math.ceil(self._until - self._clock()))

    def require_available(self) -> None:
        with self._lock:
            if self._clock() < self._until:
                self._blocked += 1
                raise QuotaUnavailable("Storage temporarily unavailable")

    def record_failure(self, error: BaseException) -> bool:
        if not is_quota_error(error):
            return False
        with self._lock:
            at = self._clock()
            # Concurrent failures must not extend the same open interval.
            if at < self._until or isinstance(error, QuotaUnavailable):
                return True
            if self._last_failure is None or at - self._last_failure >= 1800:
                self._streak = 0
            self._streak = min(self._streak + 1, 4)
            self._last_failure = at
            self._until = at + min(600, 120 * 2 ** (self._streak - 1))
            self._trips += 1
        return True

    def metrics(self) -> dict[str, int]:
        with self._lock:
            return {
                "quota_trips": self._trips,
                "quota_blocked": self._blocked,
                "quota_retry_after_s": max(0, math.ceil(self._until - self._clock())),
            }


quota = QuotaCircuit()
