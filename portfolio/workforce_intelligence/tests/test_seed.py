from datetime import date

from workforce_intelligence.contracts import change_fte
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import AuditActor, ensure_dataset, reset_dataset
from workforce_intelligence.migrations import SOURCE_TABLES
from workforce_intelligence.seed import INTERVIEW_SEED


def source_snapshot(database):
    with database.transaction() as connection:
        return {
            table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
            for table in SOURCE_TABLES
        }


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
        assert [tuple(row) for row in people] == [
            (f"Demo {letter}.", order) for order, letter in enumerate("ABCDEFGHIJKLMNO", start=1)
        ]
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
