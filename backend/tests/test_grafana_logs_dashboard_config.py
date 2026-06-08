import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
LOGS_DASHBOARD_PATH = (
    ROOT_DIR / "infra" / "observability" / "grafana" / "dashboards" / "backend-logs.json"
)


def test_backend_logs_dashboard_uses_loki_datasource() -> None:
    dashboard = _load_dashboard()
    dashboard_text = LOGS_DASHBOARD_PATH.read_text(encoding="utf-8")

    assert dashboard["uid"] == "portfolio-backend-logs"
    assert dashboard["title"] == "Portfolio Backend Logs"
    assert '"pluginId": "loki"' in dashboard_text
    assert '"type": "loki"' in dashboard_text
    assert "${DS_LOKI}" in dashboard_text


def test_backend_logs_dashboard_contains_expected_panels() -> None:
    dashboard = _load_dashboard()
    panel_titles = {panel["title"] for panel in dashboard["panels"]}

    assert "Logs" in panel_titles
    assert "Errors" in panel_titles
    assert "Warnings" in panel_titles
    assert "Logs by level" in panel_titles
    assert "Errors by event" in panel_titles
    assert "Recent errors" in panel_titles
    assert "Recent warnings" in panel_titles
    assert "Recent warning and error logs" in panel_titles


def test_backend_logs_dashboard_queries_use_dynamic_time_range() -> None:
    dashboard = _load_dashboard()
    expressions = "\n".join(
        target["expr"] for panel in dashboard["panels"] for target in panel.get("targets", [])
    )

    assert "$__range" in expressions
    assert "$__interval" in expressions
    assert "[1d]" not in expressions
    assert "[7d]" not in expressions
    assert 'service="portfolio-backend"' in expressions
    assert 'environment=~"${environment:regex}"' in expressions
    assert 'level=~"${level:regex}"' in expressions


def test_backend_logs_dashboard_does_not_store_secrets() -> None:
    dashboard_text = LOGS_DASHBOARD_PATH.read_text(encoding="utf-8").casefold()

    assert "loki_token" not in dashboard_text
    assert "bearer " not in dashboard_text
    assert "authorization" not in dashboard_text
    assert "api_key" not in dashboard_text
    assert "access policy token" not in dashboard_text


def test_backend_logs_dashboard_keeps_request_id_out_of_labels() -> None:
    dashboard_text = LOGS_DASHBOARD_PATH.read_text(encoding="utf-8")

    assert "request_id=~" not in dashboard_text
    assert 'request_id="' not in dashboard_text
    assert '| json | request_id="req_..."' not in dashboard_text


def _load_dashboard() -> dict[str, object]:
    return json.loads(LOGS_DASHBOARD_PATH.read_text(encoding="utf-8"))
