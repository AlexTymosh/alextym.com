from fastapi.testclient import TestClient

from app.main import app


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
    assert body["vector_db"] in {"configured", "not_configured"}
    assert body["llm_config"] in {"configured", "not_configured"}
    assert body["contact_email"] in {"configured", "not_configured"}


def test_warmup_returns_warmed() -> None:
    response = client.get("/api/warmup")

    assert response.status_code == 200
    assert response.json()["status"] == "warmed"
    assert response.json()["app"] == "ready"
