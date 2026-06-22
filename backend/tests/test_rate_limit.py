from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.api.rate_limit import client_identifier_from_request
from app.services.rate_limit import (
    InMemoryDailyRateLimiter,
    MisconfiguredDailyRateLimiter,
    RateLimitExceeded,
    RateLimitStoreError,
    UpstashRedisDailyRateLimiter,
)


def test_in_memory_daily_rate_limiter_rejects_after_limit() -> None:
    limiter = InMemoryDailyRateLimiter()

    first_result = limiter.check(scope="chat", identifier="127.0.0.1", limit=1)

    assert first_result.remaining == 0
    with pytest.raises(RateLimitExceeded):
        limiter.check(scope="chat", identifier="127.0.0.1", limit=1)


def test_redis_daily_rate_limiter_uses_hashed_key_and_utc_ttl() -> None:
    now = datetime(2026, 5, 28, 10, 0, 0, tzinfo=UTC)
    executor = FakeRedisExecutor()

    limiter = UpstashRedisDailyRateLimiter(
        rest_url="https://example.upstash.io",
        rest_token="token",
        executor=executor,
        now_provider=lambda: now,
    )

    result = limiter.check(scope="chat", identifier="203.0.113.10", limit=2)

    assert result.remaining == 1
    assert len(executor.commands) == 2

    increment_command = executor.commands[0]
    expire_command = executor.commands[1]
    key = increment_command[1]

    assert increment_command == ["INCR", key]
    assert expire_command == ["EXPIRE", key, 50400]
    assert key.startswith("rate-limit:daily:chat:2026-05-28:")
    assert "203.0.113.10" not in key


def test_redis_daily_rate_limiter_rejects_after_limit() -> None:
    limiter = UpstashRedisDailyRateLimiter(
        rest_url="https://example.upstash.io",
        rest_token="token",
        executor=FakeRedisExecutor(),
        now_provider=lambda: datetime(2026, 5, 28, 10, 0, 0, tzinfo=UTC),
    )

    limiter.check(scope="contact", identifier="127.0.0.1", limit=1)

    with pytest.raises(RateLimitExceeded):
        limiter.check(scope="contact", identifier="127.0.0.1", limit=1)


def test_redis_daily_rate_limiter_rejects_invalid_redis_result() -> None:
    limiter = UpstashRedisDailyRateLimiter(
        rest_url="https://example.upstash.io",
        rest_token="token",
        executor=lambda _: "not-an-integer",
    )

    with pytest.raises(RateLimitStoreError):
        limiter.check(scope="chat", identifier="127.0.0.1", limit=1)


def test_misconfigured_daily_rate_limiter_fails_explicitly() -> None:
    limiter = MisconfiguredDailyRateLimiter()

    with pytest.raises(RateLimitStoreError):
        limiter.check(scope="chat", identifier="127.0.0.1", limit=1)


def test_client_identifier_prefers_first_forwarded_for_ip() -> None:
    request = _request(
        headers={
            "x-forwarded-for": "203.0.113.10, 10.0.0.1",
            "x-real-ip": "198.51.100.20",
        },
        client_host="127.0.0.1",
    )

    assert client_identifier_from_request(request) == "203.0.113.10"


def test_client_identifier_uses_real_ip_when_forwarded_for_is_blank() -> None:
    request = _request(
        headers={
            "x-forwarded-for": "   ",
            "x-real-ip": "198.51.100.20",
        },
        client_host="127.0.0.1",
    )

    assert client_identifier_from_request(request) == "198.51.100.20"


def test_client_identifier_falls_back_to_request_client_host() -> None:
    request = _request(headers={}, client_host="127.0.0.1")

    assert client_identifier_from_request(request) == "127.0.0.1"


def test_client_identifier_returns_unknown_without_client_host() -> None:
    request = _request(headers={}, client_host=None)

    assert client_identifier_from_request(request) == "unknown"


class FakeRedisExecutor:
    def __init__(self) -> None:
        self.commands: list[list[object]] = []
        self.counts: dict[str, int] = {}

    def __call__(self, command: list[object]) -> object:
        self.commands.append(command)

        if command[0] == "INCR":
            key = str(command[1])
            next_count = self.counts.get(key, 0) + 1
            self.counts[key] = next_count
            return next_count

        if command[0] == "EXPIRE":
            return 1

        raise AssertionError(f"Unexpected command: {command}")


def _request(
    *,
    headers: dict[str, str],
    client_host: str | None,
) -> SimpleNamespace:
    client = SimpleNamespace(host=client_host) if client_host is not None else None
    return SimpleNamespace(headers=headers, client=client)
