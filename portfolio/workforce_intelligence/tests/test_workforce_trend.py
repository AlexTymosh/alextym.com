"""Monthly Workforce trend: independent effective-dated reconciliation."""

from datetime import date

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from workforce_intelligence.analytics import reporting_window
from workforce_intelligence.contracts import change_fte
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import AuditActor, current_dataset, ensure_dataset
from workforce_intelligence.http import get_database
from workforce_intelligence.router import router
from workforce_intelligence.scale_seed import FULL_SEED
from workforce_intelligence.seed import INTERVIEW_SEED
from workforce_intelligence.workforce_trend import workforce_trend


@pytest.fixture(scope="module")
def full_dataset(tmp_path_factory):
    database = Database(tmp_path_factory.mktemp("trend") / "workforce.sqlite3")
    ensure_dataset(database, FULL_SEED)
    return database


def test_full_history_reconciles_effective_budget_and_employment(full_dataset):
    with full_dataset.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, date(2026, 10, 31), date(2023, 11, 1))
        report = workforce_trend(connection, window)
        assert len(report.points) == 36
        assert report.points[0].month_key == "2023-11"
        assert report.points[-1].as_of_date == "2026-10-31"
        assert all(not point.partial_period for point in report.points)
        for point in (report.points[0], report.points[14], report.points[-1]):
            day = point.as_of_date
            budget, staff = connection.execute(
                """
                SELECT
                  (SELECT SUM(budget_fte_milli) FROM establishment_history
                   WHERE valid_from <= :day AND (valid_to IS NULL OR valid_to > :day)),
                  (SELECT COALESCE(SUM(contracted_fte_milli), 0)
                   FROM silver_substantive_employment
                   WHERE valid_from <= :day AND (valid_to IS NULL OR valid_to > :day))
                """,
                {"day": day},
            ).fetchone()
            assert point.budgeted_wte == (budget / 1000 if budget is not None else None)
            assert point.substantive_wte == staff / 1000
            assert point.workforce_gap_wte == (budget - staff) / 1000
        count_starts = connection.execute(
            "SELECT COUNT(*) FROM silver_starters WHERE started_on BETWEEN ? AND ?",
            (window.start.isoformat(), window.end.isoformat()),
        ).fetchone()[0]
        count_leavers = connection.execute(
            "SELECT COUNT(*) FROM leaver_events WHERE leaving_date BETWEEN ? AND ?",
            (window.start.isoformat(), window.end.isoformat()),
        ).fetchone()[0]
        assert sum(point.new_starters for point in report.points) == count_starts
        assert sum(point.leavers for point in report.points) == count_leavers


def test_partial_month_and_cutoff_do_not_include_future_events(full_dataset):
    with full_dataset.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, date(2026, 10, 10), date(2026, 9, 15))
        first, last = workforce_trend(connection, window).points
        assert first.month_key == "2026-09" and first.partial_period
        assert first.as_of_date == "2026-09-30"
        assert last.month_key == "2026-10" and last.partial_period
        assert last.as_of_date == "2026-10-10"
        assert (
            first.new_starters
            == connection.execute(
                "SELECT COUNT(*) FROM silver_starters WHERE started_on BETWEEN '2026-09-15' AND '2026-09-30'"
            ).fetchone()[0]
        )
        assert (
            last.new_starters
            == connection.execute(
                "SELECT COUNT(*) FROM silver_starters WHERE started_on BETWEEN '2026-10-01' AND '2026-10-10'"
            ).fetchone()[0]
        )
        assert (
            last.leavers
            == connection.execute(
                "SELECT COUNT(*) FROM leaver_events WHERE leaving_date BETWEEN '2026-10-01' AND '2026-10-10'"
            ).fetchone()[0]
        )
        substantive = connection.execute(
            """
            SELECT COALESCE(SUM(contracted_fte_milli), 0)
            FROM silver_substantive_employment
            WHERE valid_from <= '2026-10-10' AND (valid_to IS NULL OR valid_to > '2026-10-10')
            """
        ).fetchone()[0]
        assert last.substantive_wte == substantive / 1000


def test_committed_contract_change_updates_only_affected_month(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    state = ensure_dataset(database, INTERVIEW_SEED)
    with database.transaction() as connection:
        window = reporting_window(state, date(2026, 10, 31), date(2026, 9, 1))
        before = workforce_trend(connection, window).points
    updated, _ = change_fte(
        database,
        employee_id="emp-001",
        record_version=1,
        effective_from=date(2026, 10, 20),
        fte_milli=800,
        expected=state,
        actor=AuditActor("test-member", "trend-contract-change"),
    )
    with database.transaction() as connection:
        after = workforce_trend(connection, window).points
        assert current_dataset(connection).revision == updated.revision
        assert after[0] == before[0]
        assert after[1].substantive_wte == pytest.approx(before[1].substantive_wte - 0.2)
        assert after[1].workforce_gap_wte == pytest.approx(before[1].workforce_gap_wte + 0.2)


def test_trend_api_returns_quality_and_revision(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    state = ensure_dataset(database, INTERVIEW_SEED)

    def authorised_member(request: Request) -> None:
        request.state.workforce_uid = "test-member"
        request.state.request_id = "req_trend"

    app = FastAPI()
    app.include_router(router, dependencies=[Depends(authorised_member)], prefix="/api")
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(app, base_url="https://backend.test/api/workforce/") as client:
        response = client.get(
            "analytics/workforce-trend",
            params={"period_start": "2026-09-01", "as_of_date": "2026-10-31"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["dataset"]["revision"] == state.revision
        assert body["synthetic"] is True
        assert body["quality_status"] in ("passed", "review_required")
        assert len(body["trend"]["points"]) == 2
        history = client.get("analytics/workforce-trend").json()["trend"]["points"]
        assert [point["month_key"] for point in history] == [
            "2026-07",
            "2026-08",
            "2026-09",
            "2026-10",
        ]
        assert (
            client.get(
                "analytics/workforce-trend",
                params={"period_start": "2026-10-30", "as_of_date": "2026-10-01"},
            ).status_code
            == 422
        )
