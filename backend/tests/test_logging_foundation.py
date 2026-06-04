import json
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware


def test_request_id_header_is_added_to_responses(monkeypatch):
    client = _build_client(monkeypatch)
    response = client.get("/api/health/live")

    request_id = response.headers["X-Request-ID"]
    assert response.status_code == 200
    assert re.fullmatch(r"req_[a-f0-9]{32}", request_id)


def test_valid_incoming_request_id_is_reused(monkeypatch):
    client = _build_client(monkeypatch)
    response = client.get(
        "/api/health/live",
        headers={"X-Request-ID": "req_external-1234567890"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req_external-1234567890"


def test_http_request_log_contains_required_fields(monkeypatch, capsys):
    client = _build_client(
        monkeypatch,
        service_name="test-backend",
        service_version="9.9.9",
    )
    response = client.get("/api/health/live")

    assert response.status_code == 200
    log_record = _last_json_log(capsys.readouterr().out)

    assert log_record["event"] == "http.request.completed"
    assert log_record["message"] == "HTTP request completed."
    assert log_record["level"] == "INFO"
    assert log_record["service"] == "test-backend"
    assert log_record["service_version"] == "9.9.9"
    assert log_record["environment"] == "test"
    assert log_record["request_id"] == response.headers["X-Request-ID"]
    assert log_record["method"] == "GET"
    assert log_record["route"] == "/api/health/live"
    assert log_record["status_code"] == 200
    assert log_record["status_class"] == "2xx"
    assert isinstance(log_record["duration_ms"], int)
    assert log_record["duration_ms"] >= 0
    assert isinstance(log_record["timestamp"], str)
    assert log_record["timestamp"].endswith("Z")


def test_request_logging_does_not_include_query_string(monkeypatch, capsys):
    client = _build_client(monkeypatch)
    url = "/api/health/live?email=private@example.com&message=secret-text"
    response = client.get(url)

    assert response.status_code == 200
    output = capsys.readouterr().out

    assert "private@example.com" not in output
    assert "secret-text" not in output


def _build_client(
    monkeypatch,
    *,
    service_name: str = "portfolio-backend",
    service_version: str = "0.1.0",
) -> TestClient:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("SERVICE_NAME", service_name)
    monkeypatch.setenv("SERVICE_VERSION", service_version)
    get_settings.cache_clear()

    settings = get_settings()
    configure_logging(settings)

    app = FastAPI()
    app.add_middleware(
        RequestContextMiddleware,
        request_id_header=settings.request_id_header,
    )

    @app.get("/api/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    return TestClient(app)


def _last_json_log(output: str) -> dict[str, object]:
    lines = [line for line in output.splitlines() if line.strip().startswith("{")]
    assert lines
    return json.loads(lines[-1])
