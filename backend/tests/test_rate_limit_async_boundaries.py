"""Site rate limit I/O scheduling regression tests; no Redis access."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import pytest
from starlette.concurrency import run_in_threadpool

from app.api import rate_limit


class BlockingLimiter:
    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        self.entered = entered
        self.release = release

    def check(self, *, scope: str, identifier: str, limit: int) -> None:
        self.entered.set()
        if not self.release.wait(timeout=2):
            raise TimeoutError("Test worker was not released")


def test_rate_limit_runs_off_event_loop_when_called_from_async_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    limiter = BlockingLimiter(entered, release)
    monkeypatch.setattr(rate_limit, "build_rate_limiter", lambda _settings: limiter)
    request = SimpleNamespace(
        headers={"x-forwarded-for": "forged"},
        client=SimpleNamespace(host="198.51.100.20"),
    )
    settings = SimpleNamespace(
        rate_limiting_enabled=True,
        contact_daily_limit_per_ip=3,
    )

    async def scenario() -> None:
        worker = asyncio.create_task(
            run_in_threadpool(rate_limit.enforce_contact_rate_limit, request, settings)
        )
        try:
            assert await asyncio.to_thread(entered.wait, 1.0)
            # The worker is waiting, but unrelated async work can proceed.
            await asyncio.wait_for(asyncio.sleep(0), timeout=0.2)
            assert not worker.done()
        finally:
            release.set()
            await asyncio.wait_for(worker, timeout=2.0)

    asyncio.run(scenario())


def test_rate_limit_is_per_actual_peer_not_forged_header() -> None:
    first = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10"},
        client=SimpleNamespace(host="198.51.100.20"),
    )
    second = SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.10"},
        client=SimpleNamespace(host="198.51.100.21"),
    )
    assert rate_limit.client_identifier_from_request(first) != (
        rate_limit.client_identifier_from_request(second)
    )
