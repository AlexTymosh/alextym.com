from dataclasses import replace
from datetime import date

import pytest

from workforce_intelligence import database as sqlite_store
from workforce_intelligence.contracts import change_fte, employees_at
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import AuditActor, ensure_dataset, reset_dataset
from workforce_intelligence.directory_names import FEATURED_NAMES
from workforce_intelligence.migrations import SOURCE_TABLES
from workforce_intelligence.seed import INTERVIEW_SEED, populate_core
from workforce_intelligence.surveys import link_evidence


def source_snapshot(database, tables=SOURCE_TABLES):
    with database.transaction() as connection:
        return {
            table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
            for table in tables
        }


def test_reporting_migration_keeps_the_existing_seed(tmp_path, monkeypatch):
    database = Database(tmp_path / "workforce.sqlite3")
    migrations = sqlite_store.MIGRATIONS
    monkeypatch.setattr(sqlite_store, "MIGRATIONS", migrations[:1])
    legacy = replace(INTERVIEW_SEED, seed_version="1.0", populate=populate_core)
    initial = ensure_dataset(database, legacy)
    with database.transaction(write=True) as connection:
        connection.execute("UPDATE employees SET display_name = 'Demo A.' WHERE id = 'emp-001'")
    change, _ = change_fte(
        database,
        employee_id="emp-001",
        record_version=1,
        effective_from=date(2026, 10, 20),
        fte_milli=800,
        expected=initial,
        actor=AuditActor("test-member", "req_upgrade"),
    )
    with database.transaction() as connection:
        core = {
            table: ", ".join(col[1] for col in connection.execute(f"PRAGMA table_info({table})"))
            for table in SOURCE_TABLES
        }
        core = {table: columns for table, columns in core.items() if columns}
        source = {
            table: list(
                map(
                    tuple,
                    connection.execute(f"SELECT {columns} FROM {table} ORDER BY 1"),
                )
            )
            for table, columns in core.items()
        }
    monkeypatch.setattr(sqlite_store, "MIGRATIONS", migrations)
    upgraded = ensure_dataset(database, INTERVIEW_SEED)
    assert upgraded.seed_version == INTERVIEW_SEED.seed_version
    assert upgraded.dataset_id == initial.dataset_id
    assert upgraded.dataset_generation == 1
    assert upgraded.revision == change.revision + 3
    with database.transaction() as connection:
        unchanged_tables = set(core) - {
            "employees",
            "employment_contracts",
            "organisation_assignments",
        }
        assert {
            table: list(
                map(
                    tuple,
                    connection.execute(f"SELECT {columns} FROM {table} ORDER BY 1"),
                )
            )
            for table, columns in core.items()
            if table in unchanged_tables
        } == {table: source[table] for table in unchanged_tables}
        for table in ("employment_contracts", "organisation_assignments"):
            assert [
                tuple(row)
                for row in connection.execute(
                    f"SELECT {core[table]} FROM {table} WHERE employee_id NOT LIKE 'bank-%' ORDER BY 1"
                )
            ] == source[table]
        directory = employees_at(connection, upgraded.as_of_date, 20, 0)
        assert [row["display_name"] for row in directory] == list(FEATURED_NAMES)
        assert directory[0]["record_version"] == 3
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM employment_contracts WHERE employee_id LIKE 'bank-%' AND is_substantive = 0"
            ).fetchone()[0]
            == 3
        )
        assert connection.execute("SELECT COUNT(*) FROM interviews").fetchone()[0] == 6
        assert connection.execute("SELECT COUNT(*) FROM silver_applications").fetchone()[0] == 9
        assert (
            connection.execute("SELECT COUNT(*) FROM gold_reviewed_survey_findings").fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM audit_events WHERE action = 'change_fte'"
            ).fetchone()[0]
            == 1
        )


def test_directory_profile_upgrade_keeps_existing_workforce_records(tmp_path, monkeypatch):
    database = Database(tmp_path / "workforce.sqlite3")
    migrations = sqlite_store.MIGRATIONS
    monkeypatch.setattr(sqlite_store, "MIGRATIONS", migrations[:12])
    original = ensure_dataset(database, INTERVIEW_SEED)
    changed, _ = change_fte(
        database,
        employee_id="emp-001",
        record_version=1,
        effective_from=date(2026, 10, 20),
        fte_milli=800,
        expected=original,
        actor=AuditActor("test-member", "req_directory_profile_upgrade"),
    )
    source = source_snapshot(database)

    monkeypatch.setattr(sqlite_store, "MIGRATIONS", migrations)
    assert ensure_dataset(database, INTERVIEW_SEED) == changed
    assert source_snapshot(database) == source
    with database.transaction() as connection:
        directory = employees_at(connection, changed.as_of_date, 20, 0)
        assert [row["display_name"] for row in directory] == list(FEATURED_NAMES)
        assert directory[0]["contracted_fte"] == 0.8
        assert directory[0]["directory_job_title"] == "Senior Management Information Analyst"
        assert directory[-1]["directory_job_title"] == "Recruitment Co-ordinator"


def test_evidence_guard_and_gold_projection_reject_invalid_links(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    ensure_dataset(database, INTERVIEW_SEED)
    with database.transaction(write=True) as connection:
        signal = "signal-rota-002"
        for invalid in [("imaginary",), ("rota-011",), ("rota-003", "rota-003")]:
            with pytest.raises(ValueError):
                link_evidence(connection, signal, invalid)
        connection.execute(
            "INSERT INTO survey_campaigns VALUES ('other','Other','Question','2026-10-01','2026-10-30',1)"
        )
        connection.execute(
            "INSERT INTO survey_responses VALUES ('other-001','other','2026-10-01','Synthetic evidence')"
        )
        with pytest.raises(ValueError, match="ineligible"):
            link_evidence(connection, signal, ("other-001",))
        connection.execute("UPDATE ai_signals SET published_on='2026-10-30' WHERE id=?", (signal,))
        assert [
            row[0] for row in connection.execute("SELECT id FROM gold_reviewed_survey_findings")
        ] == ["signal-rota-001"]
        connection.execute(
            "INSERT INTO survey_signal_evidence VALUES ('signal-rota-001', 'other-001')"
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM gold_reviewed_survey_findings").fetchone()[0]
            == 0
        )


def test_controlled_seed_is_repeatable_across_fresh_files_and_reset(tmp_path):
    first = Database(tmp_path / "first.sqlite3")
    second = Database(tmp_path / "second.sqlite3")
    before = ensure_dataset(first, INTERVIEW_SEED)
    other = ensure_dataset(second, INTERVIEW_SEED)
    assert before.dataset_id != other.dataset_id
    assert before.scenario_code == other.scenario_code == "interview-core"
    assert before.generation_seed == other.generation_seed == INTERVIEW_SEED.generation_seed
    baseline = source_snapshot(first)
    assert source_snapshot(second) == baseline

    actor = AuditActor("test-member", "req_fixture_check")
    change_fte(
        first,
        employee_id="emp-001",
        record_version=1,
        effective_from=date(2026, 10, 20),
        fte_milli=800,
        expected=before,
        actor=actor,
    )
    assert source_snapshot(first) != baseline
    after = reset_dataset(
        first, INTERVIEW_SEED, expected=before, actor=actor, idempotency_key="reset"
    )
    assert after.dataset.dataset_generation == 2
    assert source_snapshot(first) == baseline


def test_featured_people_and_recruitment_source_events_reconcile(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    ensure_dataset(database, INTERVIEW_SEED)
    with database.transaction() as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        people = connection.execute("""
            SELECT display_name, display_order FROM employees
            WHERE is_featured_demo_employee = 1 ORDER BY display_order
        """).fetchall()
        assert [tuple(row) for row in people] == list(
            zip(FEATURED_NAMES, range(1, 21), strict=True)
        )
        events = connection.execute("""
            SELECT v.id, v.closure_kind, o.outcome, s.started_fte_milli, contract.contracted_fte_milli
            FROM vacancies v
            LEFT JOIN candidate_applications app ON app.vacancy_id = v.id
            LEFT JOIN offers o ON o.application_id = app.id
            LEFT JOIN starter_events s ON s.offer_id = o.id
            LEFT JOIN employment_contracts contract
              ON contract.employee_id = s.employee_id AND contract.valid_from = s.started_on
            WHERE app.id IN ('app-001', 'app-003', 'app-004', 'app-006')
            ORDER BY v.id
        """).fetchall()
        assert [tuple(row) for row in events] == [
            ("vac-001", None, "accepted", 1000, 1000),
            ("vac-002", "cancelled", None, None, None),
            ("vac-003", None, "accepted", None, None),
            ("vac-004", None, "accepted", 800, 800),
        ]
