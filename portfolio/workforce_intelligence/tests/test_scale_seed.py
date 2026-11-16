import calendar
import re
from dataclasses import replace
from datetime import date
from time import perf_counter

from workforce_intelligence import database as sqlite_store
from workforce_intelligence.analytics import (
    application_funnel,
    executive_metrics,
    quality_checks,
    reporting_window,
)
from workforce_intelligence.contracts import employees_at
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import advance_revision, current_dataset, ensure_dataset
from workforce_intelligence.directory_migration import has_only_directory_refresh
from workforce_intelligence.directory_names import FEATURED_NAMES
from workforce_intelligence.scale_seed import FULL_SEED


def test_full_fixture_reconciles_against_direct_sources_across_observed_history(tmp_path):
    database = Database(tmp_path / "full.sqlite3")
    start = perf_counter()
    state = ensure_dataset(database, FULL_SEED)
    assert perf_counter() - start < 10
    assert state.history_start == "2023-11-01" and state.as_of_date == "2026-10-31"
    with database.transaction() as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        for table, count in {
            "employees": 4400,
            "locations": 36,
            "organisational_units": 12,
            "roles": 27,
            "recruitment_campaigns": 36,
            "starter_events": 290,
            "survey_campaigns": 38,
        }.items():
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == count
        first_page = employees_at(conn, state.as_of_date, 21, 0)
        assert [row["display_name"] for row in first_page[:20]] == list(FEATURED_NAMES)
        assert [row["display_order"] for row in first_page[:20]] == list(range(1, 21))
        assert re.fullmatch(r"[A-Z][a-z]+ [A-Z]\.", first_page[20]["display_name"])
        assert conn.execute("SELECT COUNT(*) FROM promotion_events").fetchone()[0] > 100
        assert conn.execute("SELECT COUNT(*) FROM candidate_demographics").fetchone()[0] > 2000
        assert conn.execute("SELECT COUNT(*) FROM leaver_events").fetchone()[0] > 150
        assert conn.execute("SELECT COUNT(*) FROM absence_events").fetchone()[0] > 1000
        for index in range(36):
            year, month0 = divmod(2023 * 12 + 10 + index, 12)
            month = month0 + 1
            end = date(year, month, calendar.monthrange(year, month)[1])
            day = end.isoformat()
            assert not any(quality_checks(conn, day).values())
            direct = conn.execute(
                """SELECT SUM(contracted_fte_milli) FROM employment_contracts
                WHERE is_substantive = 1 AND valid_from <= ? AND (valid_to IS NULL OR valid_to > ?)""",
                (day, day),
            ).fetchone()[0]
            window = reporting_window(state, end, None)
            before = perf_counter()
            totals = {
                entry.definition.code: entry.current.value
                for entry in executive_metrics(conn, state, window).metrics
            }
            funnel = application_funnel(conn, window, None)
            assert perf_counter() - before < 2
            assert totals["substantive_wte"] == direct / 1000
            count = 8 + (1 if index in (34, 35) else 0)
            assert totals["new_starters"] == count
            # Cohort is by application receipt; the legacy starter in October applied in September.
            direct_cohort = conn.execute(
                "SELECT COUNT(*) FROM candidate_applications WHERE received_on BETWEEN ? AND ?",
                (window.start.isoformat(), day),
            ).fetchone()[0]
            seen = {stage.stage: stage.application_count for stage in funnel.stages}
            assert seen["received"] == direct_cohort
            assert seen["started"] == 8 + (index == 34)
    assert database.path.stat().st_size < 12 * 1024 * 1024


def test_full_fixture_changes_only_when_generation_seed_changes(tmp_path):
    def projection(name, definition):
        database = Database(tmp_path / f"{name}.sqlite3")
        ensure_dataset(database, definition)
        with database.transaction() as conn:
            return [
                tuple(row)
                for row in conn.execute("""
                SELECT e.id, p.age_band, c.contracted_fte_milli FROM employees e
                JOIN employee_profiles p ON p.employee_id = e.id
                JOIN employment_contracts c ON c.employee_id = e.id
                WHERE e.id LIKE 'demo-%' AND c.valid_to IS NULL ORDER BY e.id
            """)
            ]

    baseline = projection("controlled", FULL_SEED)
    assert projection("reproduced", FULL_SEED) == baseline
    assert projection("exploratory", replace(FULL_SEED, generation_seed=1)) != baseline


def test_upgrade_preserves_full_fixture_edits_and_analytical_sources(tmp_path, monkeypatch):
    database = Database(tmp_path / "legacy-full.sqlite3")
    migrations = sqlite_store.MIGRATIONS
    monkeypatch.setattr(sqlite_store, "MIGRATIONS", migrations[:-1])
    original = ensure_dataset(database, replace(FULL_SEED, seed_version="2.0"))
    with database.transaction(write=True) as conn:
        conn.execute(
            "UPDATE employees SET display_name = 'Demo Staff 0002.', display_order = NULL, "
            "is_featured_demo_employee = 0 WHERE id = 'demo-0002'"
        )
        conn.execute(
            "UPDATE employees SET display_name = 'Demo Staff 0005.' WHERE id = 'demo-0005'"
        )
        conn.execute("UPDATE employees SET display_name = 'Alexis V.' WHERE id = 'demo-0006'")
        demographics = conn.execute(
            "SELECT * FROM candidate_demographics ORDER BY application_id"
        ).fetchall()

    monkeypatch.setattr(sqlite_store, "MIGRATIONS", migrations)
    with database.transaction(write=True) as conn:
        updated = current_dataset(conn)
        assert updated.dataset_id == original.dataset_id
        assert updated.dataset_generation == original.dataset_generation
        assert updated.seed_version == FULL_SEED.seed_version and updated.revision == 1
        assert has_only_directory_refresh(conn, updated)
        assert not has_only_directory_refresh(conn, advance_revision(conn, updated))
        assert conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 4400
        assert (
            conn.execute("SELECT * FROM candidate_demographics ORDER BY application_id").fetchall()
            == demographics
        )
        assert [r["display_name"] for r in employees_at(conn, updated.as_of_date, 20, 0)] == list(
            FEATURED_NAMES
        )
        legacy, custom = conn.execute(
            "SELECT display_name FROM employees WHERE id IN ('demo-0005', 'demo-0006') ORDER BY id"
        ).fetchall()
        assert re.fullmatch(r"[A-Z][a-z]+ [A-Z]\.", legacy["display_name"])
        assert custom["display_name"] == "Alexis V."
