from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.metrics import configure_metrics


def test_metrics_endpoint_is_not_registered_when_disabled(monkeypatch):
    client = _build_client(monkeypatch, metrics_enabled=False)

    response = client.get("/internal/metrics")

    assert response.status_code == 404


def test_metrics_endpoint_is_not_exposed_without_token(monkeypatch):
    client = _build_client(monkeypatch, metrics_enabled=True, metrics_token="")

    response = client.get("/internal/metrics")

    assert response.status_code == 404


def test_metrics_endpoint_requires_bearer_token_and_exposes_metrics(monkeypatch):
    client = _build_client(
        monkeypatch,
        metrics_enabled=True,
        metrics_token="test-metrics-token",
    )

    client.get("/api/health/live?email=private@example.com")
    client.get("/api/items/private-item-id")

    assert client.get("/internal/metrics").status_code == 403
    assert _scrape_metrics(client, token="wrong-token").status_code == 403

    response = _scrape_metrics(client, token="test-metrics-token")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_requests_total" in response.text
    assert _has_sample(
        response.text,
        "http_requests_total",
        {"handler": "/api/health/live"},
    )
    assert "private-item-id" not in response.text
    assert "private@example.com" not in response.text


def test_metrics_endpoint_is_hidden_from_openapi(monkeypatch):
    client = _build_client(
        monkeypatch,
        metrics_enabled=True,
        metrics_token="test-metrics-token",
    )

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/internal/metrics" not in response.json()["paths"]


def _build_client(
    monkeypatch,
    *,
    metrics_enabled: bool,
    metrics_token: str = "test-metrics-token",
) -> TestClient:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("METRICS_ENABLED", "true" if metrics_enabled else "false")
    monkeypatch.setenv("METRICS_TOKEN", metrics_token)
    monkeypatch.setenv("METRICS_PATH", "/internal/metrics")
    get_settings.cache_clear()

    settings = get_settings()
    app = FastAPI()
    app.state.settings = settings

    @app.get("/api/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/items/{item_id}")
    def item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    configure_metrics(app, settings)
    return TestClient(app)


def _scrape_metrics(client: TestClient, *, token: str):
    return client.get(
        "/internal/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )


def _has_sample(
    metrics_text: str,
    metric_name: str,
    expected_labels: dict[str, str],
) -> bool:
    metric_prefix = metric_name + "{"
    for line in metrics_text.splitlines():
        if not line.startswith(metric_prefix):
            continue
        labels = _parse_labels(line)
        if all(labels.get(key) == value for key, value in expected_labels.items()):
            return True
    return False


def _parse_labels(sample_line: str) -> dict[str, str]:
    labels_start = sample_line.find("{")
    labels_end = sample_line.find("}", labels_start)
    if labels_start == -1 or labels_end == -1:
        return {}

    labels_text = sample_line[labels_start + 1 : labels_end]
    labels: dict[str, str] = {}
    for part in labels_text.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        labels[key] = value.strip('"')
    return labels
