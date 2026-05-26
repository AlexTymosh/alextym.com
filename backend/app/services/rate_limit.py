from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

from fastapi import Request


class RateLimitExceeded(Exception):
    def __init__(self, *, limit: int) -> None:
        self.limit = limit
        super().__init__("Rate limit exceeded.")


@dataclass(frozen=True)
class RateLimitResult:
    limit: int
    remaining: int


class InMemoryDailyRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counts: dict[tuple[str, str, str], int] = {}
        self._active_day = self._current_day()

    def check(self, *, scope: str, identifier: str, limit: int) -> RateLimitResult:
        if limit <= 0:
            raise RateLimitExceeded(limit=limit)

        day = self._current_day()
        key = (scope, identifier, day)

        with self._lock:
            if day != self._active_day:
                self._counts.clear()
                self._active_day = day

            current_count = self._counts.get(key, 0)
            if current_count >= limit:
                raise RateLimitExceeded(limit=limit)

            next_count = current_count + 1
            self._counts[key] = next_count
            return RateLimitResult(limit=limit, remaining=limit - next_count)

    def reset(self) -> None:
        with self._lock:
            self._counts.clear()
            self._active_day = self._current_day()

    @staticmethod
    def _current_day() -> str:
        return datetime.now(UTC).date().isoformat()


def client_identifier_from_request(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_forwarded_ip = forwarded_for.split(",", 1)[0].strip()
        if first_forwarded_ip:
            return first_forwarded_ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


_rate_limiter = InMemoryDailyRateLimiter()


def get_rate_limiter() -> InMemoryDailyRateLimiter:
    return _rate_limiter
