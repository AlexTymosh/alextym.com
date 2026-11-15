"""PR5: server-side conformed views and independent KPI reconciliation."""

from datetime import date

import pytest

from workforce_intelligence.analytics import executive_metrics, reporting_window
from workforce_intelligence.contracts import change_fte
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import (
    AuditActor,
    current_dataset,
    ensure_dataset,
    reset_dataset,
)
from workforce_intelligence.metric_catalogue import CATALOGUE
from workforce_intelligence.scale_seed import FULL_SEED
from workforce_intelligence.seed import INTERVIEW_SEED


@pytest.fixture(scope="module")
def full_dataset(tmp_path_factory):
    database = Database(tmp_path_factory.mktemp("conformed") / "workforce.sqlite3")
    ensure_dataset(database, FULL_SEED)
    return database


def test_monthly_snapshot_reconciles_direct_effective_employment(full_dataset):
    with full_dataset.transaction() as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        observed_months = connection.execute(
            "SELECT COUNT(DISTINCT month_key) FROM fact_employee_monthly_snapshot"
        ).fetchone()[0]
        assert observed_months == 36
        for day in ("2023-11-30", "2024-10-31", "2026-10-31"):
            projected = connection.execute(
                """
                SELECT COALESCE(SUM(contracted_fte_milli), 0)
                FROM fact_employee_monthly_snapshot WHERE month_end = ?
                """,
                (day,),
            ).fetchone()[0]
            direct = connection.execute(
                """
                SELECT COALESCE(SUM(contracted_fte_milli), 0)
                FROM silver_substantive_employment
                WHERE valid_from <= :day AND (valid_to IS NULL OR valid_to > :day)
                """,
                {"day": day},
            ).fetchone()[0]
            assert projected == direct
        duplicated = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT month_end, employee_id FROM fact_employee_monthly_snapshot
                GROUP BY month_end, employee_id HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        assert duplicated == 0


def test_conformed_facts_preserve_application_and_offer_grain(full_dataset):
    with full_dataset.transaction() as connection:
        for fact, source in (
            ("fact_application", "silver_applications"),
            ("fact_application_stage_event", "silver_application_events"),
            ("fact_offer", "silver_offers"),
            ("fact_new_starter", "silver_starters"),
            ("fact_leaver", "leaver_events"),
            ("fact_internal_progression", "promotion_events"),
            ("fact_learning", "learning_events"),
            ("fact_pdr", "pdr_events"),
        ):
            projected = connection.execute(f"SELECT COUNT(*) FROM {fact}").fetchone()[0]
            direct = connection.execute(f"SELECT COUNT(*) FROM {source}").fetchone()[0]
            assert projected == direct
        for dimension, size in (("dim_organisation", 12), ("dim_location", 36), ("dim_role", 27)):
            assert connection.execute(f"SELECT COUNT(*) FROM {dimension}").fetchone()[0] == size


def test_outcomes_reconcile_cohorts_to_direct_facts(full_dataset):
    with full_dataset.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, date(2026, 10, 31), date(2023, 11, 1))
        report = executive_metrics(connection, state, window)
        metrics = {item.definition.code: item.current for item in report.metrics}
        required = (
            "offer_to_start_conversion",
            "early_attrition_12m",
            "internal_appointment_rate",
            "retention_rate",
            "new_leavers",
            "internal_progressions",
            "pdr_completion_rate",
            "learning_completion_rate",
            "probation_pass_rate",
        )
        assert set(required) <= CATALOGUE.keys()
        assert all(code in metrics for code in required)
        offered = connection.execute(
            """
            SELECT COUNT(*) FROM fact_offer
            WHERE outcome = 'accepted' AND resolved_on BETWEEN ? AND ?
            """,
            (window.start.isoformat(), window.end.isoformat()),
        ).fetchone()[0]
        assert metrics["offer_to_start_conversion"].denominator == offered
        leavers = connection.execute("SELECT COUNT(*) FROM fact_leaver").fetchone()[0]
        assert metrics["new_leavers"].value == leavers
        for code in required:
            observation = metrics[code]
            assert observation.status in ("available", "unavailable")
            if code.endswith(("rate", "conversion", "_12m")):
                if observation.value is not None:
                    assert 0 <= observation.value <= 100


def test_insufficient_followup_is_unavailable_not_zero(full_dataset):
    with full_dataset.transaction() as connection:
        state = current_dataset(connection)
        window = reporting_window(state, date(2026, 10, 31), date(2026, 10, 1))
        metrics = {
            item.definition.code: item.current
            for item in executive_metrics(connection, state, window).metrics
        }
        early = metrics["early_attrition_12m"]
        assert early.value is None
        assert early.status == "unavailable"
        assert early.denominator == 0
        assert metrics["new_leavers"].value is not None


def test_monthly_fact_updates_after_committed_fte_change_and_reset(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    state = ensure_dataset(database, INTERVIEW_SEED)
    with database.transaction() as connection:
        before = connection.execute(
            """
            SELECT SUM(contracted_fte_milli) FROM fact_employee_monthly_snapshot
            WHERE month_end = '2026-10-31'
            """
        ).fetchone()[0]
        old = connection.execute(
            """
            SELECT SUM(contracted_fte_milli) FROM fact_employee_monthly_snapshot
            WHERE month_end = '2026-09-30'
            """
        ).fetchone()[0]
        revisions = connection.execute(
            "SELECT DISTINCT source_revision FROM fact_employee_monthly_snapshot"
        ).fetchall()
        assert [row[0] for row in revisions] == [state.revision]
    updated, _ = change_fte(
        database,
        employee_id="emp-001",
        record_version=1,
        effective_from=date(2026, 10, 20),
        fte_milli=800,
        expected=state,
        actor=AuditActor("test-member", "analytics-commit-13"),
    )
    with database.transaction() as connection:
        current = connection.execute(
            """
            SELECT SUM(contracted_fte_milli) FROM fact_employee_monthly_snapshot
            WHERE month_end = '2026-10-31'
            """
        ).fetchone()[0]
        prior = connection.execute(
            """
            SELECT SUM(contracted_fte_milli) FROM fact_employee_monthly_snapshot
            WHERE month_end = '2026-09-30'
            """
        ).fetchone()[0]
        assert current == before - 200
        assert prior == old
        assert (
            connection.execute(
                "SELECT DISTINCT source_revision FROM fact_employee_monthly_snapshot"
            ).fetchone()[0]
            == updated.revision
        )
    replacement = reset_dataset(
        database,
        INTERVIEW_SEED,
        expected=updated,
        actor=AuditActor("test-member", "analytics-reset"),
        idempotency_key="analytics-reset-01",
    )
    with database.transaction() as connection:
        assert (
            connection.execute(
                """
            SELECT SUM(contracted_fte_milli) FROM fact_employee_monthly_snapshot
            WHERE month_end = '2026-10-31'
            """
            ).fetchone()[0]
            == before
        )
        assert (
            connection.execute(
                "SELECT DISTINCT dataset_generation FROM fact_employee_monthly_snapshot"
            ).fetchone()[0]
            == replacement.dataset.dataset_generation
        )
