from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
import hashlib
import json
import re
from threading import Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from app.core.config import Settings

RATE_LIMIT_KEY_PREFIX = "rate-limit:daily"
UPSTASH_REDIS_TIMEOUT_SECONDS = 10.0


class RateLimitExceeded(Exception):
    def __init__(self, *, limit: int) -> None:
        self.limit = limit
        super().__init__("Rate limit exceeded.")


class RateLimitStoreError(Exception):
    pass


@dataclass(frozen=True)
class RateLimitResult:
    limit: int
    remaining: int


class DailyRateLimiter:
    def check(self, *, scope: str, identifier: str, limit: int) -> RateLimitResult:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


class InMemoryDailyRateLimiter(DailyRateLimiter):
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


class MisconfiguredDailyRateLimiter(DailyRateLimiter):
    def check(self, *, scope: str, identifier: str, limit: int) -> RateLimitResult:
        raise RateLimitStoreError("Redis rate limiting is partially configured.")

    def reset(self) -> None:
        return None


class UpstashRedisDailyRateLimiter(DailyRateLimiter):
    def __init__(
        self,
        *,
        rest_url: str,
        rest_token: str,
        timeout_seconds: float = UPSTASH_REDIS_TIMEOUT_SECONDS,
        executor: Callable[[list[Any]], Any] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._rest_url = rest_url.rstrip("/")
        self._rest_token = rest_token
        self._timeout_seconds = timeout_seconds
        self._executor = executor or self._execute_sync
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    def check(self, *, scope: str, identifier: str, limit: int) -> RateLimitResult:
        if limit <= 0:
            raise RateLimitExceeded(limit=limit)

        now = _ensure_utc_datetime(self._now_provider())
        key = _redis_daily_key(scope=scope, identifier=identifier, now=now)
        count = _coerce_int(self._execute(["INCR", key]))
        ttl_seconds = _seconds_until_next_utc_day(now)

        self._execute(["EXPIRE", key, ttl_seconds])

        if count > limit:
            raise RateLimitExceeded(limit=limit)

        return RateLimitResult(limit=limit, remaining=max(limit - count, 0))

    def reset(self) -> None:
        return None

    def _execute(self, command: list[Any]) -> Any:
        try:
            return self._executor(command)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RateLimitStoreError("Redis rate limit command failed.") from exc

    def _execute_sync(self, command: list[Any]) -> Any:
        payload = json.dumps(command, separators=(",", ":")).encode("utf-8")
        request = UrlRequest(
            self._rest_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._rest_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urlopen(request, timeout=self._timeout_seconds) as response:
            response_body = response.read().decode("utf-8")

        try:
            decoded_response = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise RateLimitStoreError("Redis REST response was not valid JSON.") from exc

        if not isinstance(decoded_response, dict):
            raise RateLimitStoreError("Redis REST response had an unexpected shape.")

        if "error" in decoded_response:
            raise RateLimitStoreError("Redis REST command failed.")

        return decoded_response.get("result")


def build_rate_limiter(settings: Settings) -> DailyRateLimiter:
    upstash_values = (
        settings.upstash_redis_rest_url,
        settings.upstash_redis_rest_token,
    )
    if all(upstash_values):
        return UpstashRedisDailyRateLimiter(
            rest_url=settings.upstash_redis_rest_url,
            rest_token=settings.upstash_redis_rest_token,
        )
    if any(upstash_values):
        return MisconfiguredDailyRateLimiter()

    return get_rate_limiter()


def _redis_daily_key(*, scope: str, identifier: str, now: datetime) -> str:
    day = now.date().isoformat()
    safe_scope = _safe_key_part(scope)
    identifier_hash = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"{RATE_LIMIT_KEY_PREFIX}:{safe_scope}:{day}:{identifier_hash}"


def _safe_key_part(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9:_-]+", "_", value.strip()) or "unknown"


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        raise RateLimitStoreError("Redis returned a boolean where an integer was expected.")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise RateLimitStoreError("Redis returned a non-integer string.") from exc

    raise RateLimitStoreError("Redis returned a non-integer result.")


def _ensure_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _seconds_until_next_utc_day(now: datetime) -> int:
    next_day = now.date() + timedelta(days=1)
    next_midnight = datetime.combine(next_day, time.min, tzinfo=UTC)
    return max(1, int((next_midnight - now).total_seconds()))


_rate_limiter = InMemoryDailyRateLimiter()


def get_rate_limiter() -> InMemoryDailyRateLimiter:
    return _rate_limiter
