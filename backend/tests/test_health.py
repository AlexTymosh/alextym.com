from dataclasses import replace

from fastapi.testclient import TestClient

from app.api.health import get_health_service
from app.core.config import get_settings
from app.main import app
from app.rag.readiness import RagReadinessResult
from app.services.health import HealthService


client = TestClient(app)


def test_live_returns_alive() -> None:
    response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_ready_returns_structured_response() -> None:
    response = client.get("/api/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["app"] == "ready"
    assert body["environment"]
    assert body["vector_db"] in {"ready", "not_ready", "not_configured"}
    assert body["llm_config"] in {"configured", "not_configured"}
    assert body["contact_email"] in {"configured", "not_configured"}


def test_warmup_returns_warmed() -> None:
    response = client.get("/api/warmup")

    assert response.status_code == 200
    assert response.json()["status"] == "warmed"
    assert response.json()["app"] == "ready"


def test_ready_returns_503_when_qdrant_contract_is_not_ready() -> None:
    settings = replace(
        get_settings(),
        qdrant_url="https://qdrant.example",
        qdrant_api_key="configured",
    )
    service = HealthService(
        settings,
        rag_readiness_probe=FakeReadinessProbe(
            RagReadinessResult(
                status="not_ready",
                error_code="payload_index_missing",
            )
        ),
    )
    app.dependency_overrides[get_health_service] = lambda: service

    try:
        response = client.get("/api/health/ready")
    finally:
        app.dependency_overrides.pop(get_health_service, None)

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["vector_db"] == "not_ready"
    assert "payload_index_missing" not in response.text


class FakeReadinessProbe:
    def __init__(self, result: RagReadinessResult) -> None:
        self._result = result

    def check(self) -> RagReadinessResult:
        return self._result
