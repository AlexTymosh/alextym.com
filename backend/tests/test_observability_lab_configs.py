import json
from pathlib import Path
from typing import Any

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
    panel_titles = {_panel_title(panel) for panel in _dashboard_panels(dashboard)}
    expressions = "\n".join(_dashboard_expressions(dashboard))

    assert "Backend scrape status" in panel_titles
    assert "HTTP requests" in panel_titles
    assert "HTTP 5xx" in panel_titles
    assert "Chat requests" in panel_titles
    assert "Page views" in panel_titles
    assert "Resume downloads" in panel_titles
    assert "HTTP requests by handler" in panel_titles
    assert "HTTP p95 latency by handler" in panel_titles
    assert "Chat requests by outcome" in panel_titles
    assert "RAG retrieval p95 latency" in panel_titles
    assert "LLM requests by outcome" in panel_titles
    assert "Contact submissions" in panel_titles
    assert "Escalation events" in panel_titles
    assert "Rate limit checks" in panel_titles
    assert "Page views by page" in panel_titles
    assert "Resume downloads by source" in panel_titles

    assert 'up{job=~"$job"}' in expressions
    assert "http_requests_total" in expressions
    assert "http_request_duration_seconds_bucket" in expressions
    assert "portfolio_chat_requests_total" in expressions
    assert "portfolio_rag_retrieval_duration_seconds_bucket" in expressions
    assert "portfolio_llm_requests_total" in expressions
    assert "portfolio_rate_limit_checks_total" in expressions
    assert "portfolio_page_views_total" in expressions
    assert "portfolio_resume_downloads_total" in expressions


def test_observability_dashboard_uses_dynamic_time_ranges() -> None:
    dashboard = json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))
    panel_titles = {_panel_title(panel) for panel in _dashboard_panels(dashboard)}
    expressions = "\n".join(_dashboard_expressions(dashboard))
    axis_labels = "\n".join(_dashboard_axis_labels(dashboard))

    assert "$__range" in expressions
    assert "$__rate_interval" in expressions
    assert "[7d]" not in expressions
    assert "[1d]" not in expressions
    assert not any("/ 7d" in title for title in panel_titles)
    assert not any(title.startswith("Daily ") for title in panel_titles)
    assert not any("1d window" in title for title in panel_titles)
    assert "daily count" not in axis_labels


def test_taskfile_contains_observability_tasks() -> None:
    taskfile_text = (ROOT_DIR / "Taskfile.yml").read_text(encoding="utf-8")

    assert "OBSERVABILITY_COMPOSE:" in taskfile_text
    assert "obs:config:" in taskfile_text
    assert "obs:up:" in taskfile_text
    assert "obs:down:" in taskfile_text
    assert "obs:logs:" in taskfile_text
    assert "obs:restart:" in taskfile_text


def _dashboard_panels(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    if "panels" in dashboard:
        return list(dashboard["panels"])

    elements = dashboard.get("spec", {}).get("elements", {})
    return [
        element.get("spec", {}) for element in elements.values() if element.get("kind") == "Panel"
    ]


def _dashboard_expressions(dashboard: dict[str, Any]) -> list[str]:
    expressions: list[str] = []
    for panel in _dashboard_panels(dashboard):
        expressions.extend(_legacy_panel_expressions(panel))
        expressions.extend(_grafana_v2_panel_expressions(panel))
    return expressions


def _legacy_panel_expressions(panel: dict[str, Any]) -> list[str]:
    return [target.get("expr", "") for target in panel.get("targets", []) if target.get("expr")]


def _grafana_v2_panel_expressions(panel: dict[str, Any]) -> list[str]:
    queries = panel.get("data", {}).get("spec", {}).get("queries", [])
    expressions: list[str] = []
    for query in queries:
        expr = query.get("spec", {}).get("query", {}).get("spec", {}).get("expr")
        if expr:
            expressions.append(expr)
    return expressions


def _dashboard_axis_labels(dashboard: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for panel in _dashboard_panels(dashboard):
        custom_config = (
            panel.get("vizConfig", {})
            .get("spec", {})
            .get("fieldConfig", {})
            .get("defaults", {})
            .get("custom", {})
        )
        axis_label = custom_config.get("axisLabel")
        if axis_label:
            labels.append(axis_label)
    return labels


def _panel_title(panel: dict[str, Any]) -> str:
    return panel.get("title", "")
