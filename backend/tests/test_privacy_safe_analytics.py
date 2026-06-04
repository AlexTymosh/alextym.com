from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.analytics import router as analytics_router
from app.core.config import get_settings
from app.core.metrics import configure_metrics


def test_page_view_metrics_record_only_whitelisted_pages(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/analytics/events",
        json={"event": "page_view", "page": "/resume"},
    )

    assert response.status_code == 202
    metrics = _scrape_metrics(client)
    assert 'portfolio_page_views_total{page="/resume"}' in metrics


def test_resume_download_metrics_record_only_whitelisted_source(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/analytics/events",
        json={"event": "resume_download", "source": "resume_page"},
    )

    assert response.status_code == 202
    metrics = _scrape_metrics(client)
    assert 'portfolio_resume_downloads_total{source="resume_page"}' in metrics


def test_analytics_rejects_unwhitelisted_page_without_metric_leak(
    monkeypatch,
) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/analytics/events",
        json={"event": "page_view", "page": "/resume?email=private@example.com"},
    )

    assert response.status_code == 422
    metrics = _scrape_metrics(client)
    assert "private@example.com" not in metrics
    assert "/resume?email" not in metrics


def test_analytics_rejects_user_level_tracking_fields(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/analytics/events",
        json={
            "event": "page_view",
            "page": "/chat",
            "visitor_id": "visitor-123",
            "user_id": "user-123",
        },
    )

    assert response.status_code == 422
    metrics = _scrape_metrics(client)
    assert "visitor-123" not in metrics
    assert "user-123" not in metrics


def _build_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("METRICS_ENABLED", "true")
    monkeypatch.setenv("METRICS_TOKEN", "test-metrics-token")
    monkeypatch.setenv("METRICS_PATH", "/internal/metrics")
    get_settings.cache_clear()

    settings = get_settings()
    app = FastAPI()
    app.state.settings = settings
    app.include_router(analytics_router, prefix="/api")
    configure_metrics(app, settings)
    return TestClient(app)


def _scrape_metrics(client: TestClient) -> str:
    response = client.get(
        "/internal/metrics",
        headers={"Authorization": "Bearer test-metrics-token"},
    )
    assert response.status_code == 200
    return response.text
