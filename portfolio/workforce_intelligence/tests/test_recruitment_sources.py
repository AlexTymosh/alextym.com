"""Recruitment source reporting: independent cohort reconciliation."""

from datetime import date

from workforce_intelligence.analytics import reporting_window
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import current_dataset, ensure_dataset
from workforce_intelligence.recruitment_sources import recruitment_sources
from workforce_intelligence.seed import INTERVIEW_SEED


def test_sources_use_distinct_applications_not_event_rows(tmp_path):
    database = Database(tmp_path / "sources.sqlite3")
    ensure_dataset(database, INTERVIEW_SEED)
    with database.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, date(2026, 10, 31), date(2026, 10, 1))
        report = recruitment_sources(connection, window)
        expected = connection.execute(
            "SELECT COUNT(*) FROM silver_applications WHERE received_on BETWEEN ? AND ?",
            (window.start.isoformat(), window.end.isoformat()),
        ).fetchone()[0]
        assert report.total_applications == expected == 5
        assert sum(row.applications for row in report.rows) == expected
        assert all(row.screened <= row.applications for row in report.rows)
        assert all(row.starters <= row.accepted_offers <= row.applications for row in report.rows)
        # Duplicate screened stage for app-004 must not produce duplicate applications.
        careers = next(row for row in report.rows if row.source_code == "careers")
        assert careers.applications == 2
        assert careers.screened == 2


def test_source_filters_reconcile_to_same_candidate_cohort(tmp_path):
    database = Database(tmp_path / "sources.sqlite3")
    ensure_dataset(database, INTERVIEW_SEED)
    with database.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, date(2026, 10, 31), date(2026, 9, 1))
        filtered = recruitment_sources(connection, window, location_id="central")
        expected = connection.execute(
            """
            SELECT COUNT(*) FROM fact_application
            WHERE received_on BETWEEN ? AND ? AND location_id = 'central'
            """,
            (window.start.isoformat(), window.end.isoformat()),
        ).fetchone()[0]
        assert filtered.total_applications == expected
        assert recruitment_sources(connection, window, campaign_id="missing").rows == []
        assert (
            recruitment_sources(connection, window, role_id="advisor").total_applications
            == expected
        )


def test_source_report_excludes_future_events(tmp_path):
    database = Database(tmp_path / "sources.sqlite3")
    ensure_dataset(database, INTERVIEW_SEED)
    with database.transaction() as connection:
        state = current_dataset(connection)
        earlier = recruitment_sources(
            connection,
            reporting_window(state, date(2026, 9, 15), date(2026, 9, 1)),
        )
        later = recruitment_sources(
            connection,
            reporting_window(state, date(2026, 10, 31), date(2026, 9, 1)),
        )
        assert earlier.total_applications <= later.total_applications
        assert sum(row.starters for row in earlier.rows) == 0
        assert sum(row.starters for row in later.rows) >= 1
