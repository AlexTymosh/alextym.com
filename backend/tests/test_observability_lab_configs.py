import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
OBSERVABILITY_DIR = ROOT_DIR / "infra" / "observability"
DASHBOARD_PATH = OBSERVABILITY_DIR / "grafana" / "dashboards" / "portfolio-observability.json"


def test_observability_compose_config_exists() -> None:
    compose_text = (OBSERVABILITY_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    assert "prom/prometheus:" in compose_text
    assert "grafana/grafana-oss:" in compose_text
    assert "9090:9090" in compose_text
    assert "3001:3000" in compose_text
    assert "host.docker.internal:host-gateway" in compose_text
    assert "./prometheus.yml:/etc/prometheus/prometheus.yml:ro" in compose_text
    assert "--storage.tsdb.retention.time=30d" in compose_text


def test_prometheus_scrapes_protected_backend_metrics() -> None:
    prometheus_text = (OBSERVABILITY_DIR / "prometheus.yml").read_text(encoding="utf-8")

    assert "job_name: portfolio-backend-local" in prometheus_text
    assert "metrics_path: /internal/metrics" in prometheus_text
    assert "authorization:" in prometheus_text
    assert "type: Bearer" in prometheus_text
    assert "credentials: local-dev-metrics-token" in prometheus_text
    assert "host.docker.internal:8000" in prometheus_text


def test_grafana_provisions_prometheus_datasource() -> None:
    datasource_path = (
        OBSERVABILITY_DIR / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
    )
    datasource_text = datasource_path.read_text(encoding="utf-8")

    assert "uid: prometheus" in datasource_text
    assert "type: prometheus" in datasource_text
    assert "url: http://prometheus:9090" in datasource_text
    assert "isDefault: true" in datasource_text


def test_grafana_dashboard_is_provisioned_from_file() -> None:
    dashboards_path = (
        OBSERVABILITY_DIR / "grafana" / "provisioning" / "dashboards" / "dashboards.yml"
    )
    dashboards_text = dashboards_path.read_text(encoding="utf-8")

    assert "name: portfolio-observability" in dashboards_text
    assert "folder: Portfolio Observability" in dashboards_text
    assert "path: /var/lib/grafana/dashboards" in dashboards_text


def test_observability_dashboard_contains_required_panels() -> None:
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    panel_titles = {panel["title"] for panel in dashboard["panels"]}
    expressions = "\n".join(
        target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", [])
    )

    assert dashboard["uid"] == "portfolio-observability"
    assert dashboard["title"] == "Portfolio Backend Observability"
    assert dashboard["time"] == {"from": "now-14d/d", "to": "now"}
    assert dashboard["refresh"] == "5m"
    assert "Backend scrape status" in panel_titles
    assert "HTTP p95 latency by handler (1d window)" in panel_titles
    assert "Daily chat requests by outcome" in panel_titles
    assert "Daily rate limit checks" in panel_titles
    assert "Page views / 7d" in panel_titles
    assert "Daily page views by page" in panel_titles
    assert "Resume downloads / 7d" in panel_titles
    assert "Daily resume downloads by source" in panel_titles
    assert 'up{job="portfolio-backend-local"}' in expressions
    assert "http_requests_total" in expressions
    assert "http_request_duration_seconds_bucket" in expressions
    assert "portfolio_chat_requests_total" in expressions
    assert "portfolio_rag_retrieval_duration_seconds_bucket" in expressions
    assert "portfolio_llm_requests_total" in expressions
    assert "portfolio_rate_limit_checks_total" in expressions
    assert "portfolio_page_views_total" in expressions
    assert "portfolio_resume_downloads_total" in expressions
    assert "increase(portfolio_page_views_total[7d])" in expressions
    assert "increase(portfolio_resume_downloads_total[7d])" in expressions
    assert "increase(portfolio_page_views_total[1d])" in expressions
    assert "increase(portfolio_resume_downloads_total[1d])" in expressions

    panels = {panel["title"]: panel for panel in dashboard["panels"]}
    assert panels["Page views / 7d"]["gridPos"]["y"] == 0
    assert panels["Resume downloads / 7d"]["gridPos"]["y"] == 0

    time_series_panels = [
        panel for panel in dashboard["panels"] if panel.get("type") == "timeseries"
    ]
    assert time_series_panels
    for panel in time_series_panels:
        custom = panel["fieldConfig"]["defaults"]["custom"]
        assert custom["drawStyle"] == "line"
        assert custom["fillOpacity"] == 10


def test_taskfile_contains_observability_tasks() -> None:
    taskfile_text = (ROOT_DIR / "Taskfile.yml").read_text(encoding="utf-8")

    assert "OBSERVABILITY_COMPOSE:" in taskfile_text
    assert "obs:config:" in taskfile_text
    assert "obs:up:" in taskfile_text
    assert "obs:down:" in taskfile_text
    assert "obs:logs:" in taskfile_text
    assert "obs:restart:" in taskfile_text
