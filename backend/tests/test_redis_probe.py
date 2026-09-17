import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.api import redis_probe as probe_api
from app.core.config import get_settings
from app.services import redis_probe as probe_module
from app.services.redis_probe import RedisProbeError, RedisProbeService


PROBE_PATH = "/internal/probes/redis"
AUTH = {"Authorization": "Bearer test-probe-secret"}
REST_URL = "https://redis.example"
REST_TOKEN = "test-provider-secret"


class FakeRedis:
    def __init__(self):
        self.commands = []
        self.values = {"existing:handoff": "visitor data", "existing:rate-limit": "5"}

    def handle(self, request):
        assert str(request.url) == REST_URL
        assert request.headers["Authorization"] == f"Bearer {REST_TOKEN}"
        command = json.loads(request.content)
        self.commands.append(command)
        action, key, *args = command
        if action == "SET":
            self.values[key] = args[0]
            result = "OK"
        elif action == "GET":
            result = self.values.get(key)
        else:
            assert action == "DEL"
            result = int(self.values.pop(key, None) is not None)
        return httpx.Response(200, json={"result": result})


def make_service(handler):
    return RedisProbeService(REST_URL, REST_TOKEN, transport=httpx.MockTransport(handler))


def make_client(monkeypatch, handler, *, token="test-probe-secret"):
    app = FastAPI()
    app.state.settings = replace(
        get_settings(),
        redis_probe_token=token,
        upstash_redis_rest_url=REST_URL,
        upstash_redis_rest_token=REST_TOKEN,
    )
    app.include_router(probe_api.router)
    monkeypatch.setattr(
        probe_api,
        "RedisProbeService",
        lambda url, secret: RedisProbeService(url, secret, transport=httpx.MockTransport(handler)),
    )
    return TestClient(app)


@pytest.mark.parametrize("header", [None, "Bearer wrong", "Basic test-probe-secret"])
def test_unauthorized_requests_do_not_contact_redis(monkeypatch, header):
    redis = FakeRedis()
    client = make_client(monkeypatch, redis.handle)
    response = client.post(PROBE_PATH, headers={"Authorization": header} if header else {})
    assert response.status_code == 403
    assert redis.commands == []


def test_missing_probe_token_disables_endpoint(monkeypatch):
    redis = FakeRedis()
    client = make_client(monkeypatch, redis.handle, token="")
    assert client.post(PROBE_PATH, headers=AUTH).status_code == 404
    assert redis.commands == []


def test_success_checks_temporary_value_and_preserves_business_keys(monkeypatch):
    redis = FakeRedis()
    original = redis.values.copy()
    client = make_client(monkeypatch, redis.handle)
    with capture_logs() as logs:
        response = client.post(PROBE_PATH, headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["Cache-Control"] == "no-store"
    assert [command[0] for command in redis.commands] == ["SET", "GET", "DEL"]
    key = redis.commands[0][1]
    assert key.startswith("system:probe:redis:")
    assert redis.commands[0][3:] == ["EX", 60]
    assert redis.commands[1:] == [["GET", key], ["DEL", key]]
    assert redis.values == original
    assert logs == [
        {
            "event": "redis_probe_succeeded",
            "duration_seconds": logs[0]["duration_seconds"],
            "log_level": "info",
        }
    ]
    assert PROBE_PATH not in client.get("/openapi.json").json()["paths"]
    assert client.get(PROBE_PATH, headers=AUTH).status_code == 405


@pytest.mark.parametrize(
    "phase, reply, expected_code",
    [
        ("SET", httpx.Response(200, json={"result": None}), "write_failed"),
        ("GET", httpx.Response(200, json={"result": "wrong value"}), "value_mismatch"),
        ("GET", httpx.Response(200, json={"result": None}), "value_mismatch"),
        ("GET", httpx.Response(200, json={"error": "private provider detail"}), "invalid_response"),
        ("GET", httpx.Response(200, json=[]), "invalid_response"),
        ("GET", httpx.Response(200, json={}), "invalid_response"),
        ("GET", httpx.Response(200, text="invalid JSON private detail"), "invalid_response"),
        ("GET", httpx.Response(401, text="private provider detail"), "http_status"),
        ("GET", httpx.Response(503, text="private provider detail"), "http_status"),
        ("DEL", httpx.Response(200, json={"result": 0}), "cleanup_failed"),
        ("DEL", httpx.Response(200, json={"result": True}), "cleanup_failed"),
        ("DEL", httpx.Response(503), "http_status"),
    ],
)
def test_failed_operations_return_safe_503_and_attempt_cleanup(
    monkeypatch, phase, reply, expected_code
):
    redis = FakeRedis()

    def handler(request):
        response = redis.handle(request)
        return reply if redis.commands[-1][0] == phase else response

    client = make_client(monkeypatch, handler)
    with capture_logs() as logs:
        response = client.post(PROBE_PATH, headers=AUTH)
    assert response.status_code == 503
    assert response.json() == {"detail": "Redis check failed"}
    assert response.headers["Cache-Control"] == "no-store"
    assert redis.commands[-1][0] == "DEL"
    assert logs == [
        {
            "event": "redis_probe_failed",
            "error_code": expected_code,
            "duration_seconds": logs[0]["duration_seconds"],
            "log_level": "warning",
        }
    ]


@pytest.mark.parametrize("error", [httpx.ConnectError, httpx.ReadTimeout])
def test_lost_write_response_still_attempts_cleanup(error):
    redis = FakeRedis()

    def handler(request):
        response = redis.handle(request)
        if redis.commands[-1][0] == "SET":
            raise error("private provider detail", request=request)
        return response

    with pytest.raises(RedisProbeError) as exc:
        asyncio.run(make_service(handler).check())
    assert exc.value.code == ("timeout" if error is httpx.ReadTimeout else "connection")
    assert [command[0] for command in redis.commands] == ["SET", "DEL"]
    assert not any(key.startswith("system:probe:") for key in redis.values)


def test_cleanup_error_does_not_hide_original_failure():
    redis = FakeRedis()

    def handler(request):
        response = redis.handle(request)
        if redis.commands[-1][0] == "GET":
            return httpx.Response(200, json={"result": None})
        if redis.commands[-1][0] == "DEL":
            raise httpx.ConnectError("cleanup unavailable", request=request)
        return response

    with pytest.raises(RedisProbeError, match="value_mismatch"):
        asyncio.run(make_service(handler).check())


def test_redirect_is_not_followed_with_provider_token():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(307, headers={"Location": "https://different.example"})

    with pytest.raises(RedisProbeError, match="http_status"):
        asyncio.run(make_service(handler).check())
    assert len(requests) == 2  # SET and best-effort DEL, both to the configured host.
    assert all(request.url.host == "redis.example" for request in requests)


@pytest.mark.parametrize(
    "url, token",
    [
        ("", REST_TOKEN),
        (REST_URL, ""),
        ("http://redis.example", REST_TOKEN),
        ("https://user:password@redis.example", REST_TOKEN),
        ("https://redis.example?token=private", REST_TOKEN),
        ("https://redis.example#fragment", REST_TOKEN),
        ("https://[invalid", REST_TOKEN),
        ("https://redis.example:invalid", REST_TOKEN),
    ],
)
def test_invalid_configuration_does_not_make_requests(url, token):
    def handler(request):
        pytest.fail("Invalid configuration must not send a request")

    service = RedisProbeService(url, token, transport=httpx.MockTransport(handler))
    with pytest.raises(RedisProbeError, match="configuration"):
        asyncio.run(service.check())


def test_timeout_budget_is_shared_by_all_operations_including_cleanup(monkeypatch):
    monkeypatch.setattr(probe_module, "REDIS_PROBE_TIMEOUT_SECONDS", 0.1)
    redis = FakeRedis()

    async def handler(request):
        # Each operation fits individually, but three do not fit the total budget.
        await asyncio.sleep(0.04)
        return redis.handle(request)

    async def run():
        with pytest.raises(RedisProbeError, match="timeout"):
            await asyncio.wait_for(make_service(handler).check(), timeout=1.0)

    asyncio.run(run())
    assert redis.commands[0][3:] == ["EX", 60]


@pytest.mark.parametrize("blocked_phase", ["SET", "GET", "DEL"])
def test_hung_operation_times_out_without_hanging_cleanup(monkeypatch, blocked_phase):
    monkeypatch.setattr(probe_module, "REDIS_PROBE_TIMEOUT_SECONDS", 0.02)
    redis = FakeRedis()

    async def handler(request):
        response = redis.handle(request)
        if redis.commands[-1][0] == blocked_phase:
            await asyncio.Event().wait()
        return response

    async def run():
        with pytest.raises(RedisProbeError, match="timeout"):
            await asyncio.wait_for(make_service(handler).check(), timeout=1.0)

    asyncio.run(run())
    assert redis.commands[0][3:] == ["EX", 60]
    assert redis.commands[-1][0] == blocked_phase


def test_concurrent_checks_use_independent_keys_without_blocking():
    redis = FakeRedis()
    original = redis.values.copy()

    async def run():
        all_writes_started = asyncio.Event()
        started_keys = []

        async def handler(request):
            command = json.loads(request.content)
            if command[0] == "SET":
                started_keys.append(command[1])
                if len(started_keys) == 3:
                    all_writes_started.set()
                await all_writes_started.wait()
            return redis.handle(request)

        await asyncio.wait_for(
            asyncio.gather(*(make_service(handler).check() for _ in range(3))), timeout=1.0
        )
        assert len(set(started_keys)) == 3

    asyncio.run(run())
    assert redis.values == original


def test_main_app_registers_probe_and_keeps_health_independent(monkeypatch):
    from app.main import app

    monkeypatch.setattr(
        app.state,
        "settings",
        replace(get_settings(), redis_probe_token="test-probe-secret"),
    )
    calls = []

    async def unavailable(self):
        calls.append("probe")
        raise RedisProbeError("connection")

    monkeypatch.setattr(RedisProbeService, "check", unavailable)
    client = TestClient(app)
    assert client.post(PROBE_PATH, headers=AUTH).status_code == 503
    assert client.get("/api/health/live").status_code == 200
    assert client.get("/api/health/ready").status_code == 200
    assert client.get("/api/warmup").status_code == 200
    assert calls == ["probe"]


def test_probe_token_is_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("REDIS_PROBE_TOKEN", "test-configured-probe-token")
    get_settings.cache_clear()
    try:
        assert get_settings().redis_probe_token == "test-configured-probe-token"
    finally:
        get_settings.cache_clear()


def test_missing_redis_configuration_returns_503_after_authentication(monkeypatch):
    redis = FakeRedis()
    client = make_client(monkeypatch, redis.handle)
    monkeypatch.setattr(
        client.app.state,
        "settings",
        replace(client.app.state.settings, upstash_redis_rest_token=""),
    )
    assert client.post(PROBE_PATH).status_code == 403
    response = client.post(PROBE_PATH, headers=AUTH)
    assert response.status_code == 503
    assert response.json() == {"detail": "Redis check failed"}
    assert redis.commands == []
