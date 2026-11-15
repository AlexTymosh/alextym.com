"""Vacancy ageing groups reconcile with independently derived open vacancies."""

from datetime import date

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from workforce_intelligence.analytics import executive_metrics, reporting_window
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import current_dataset, ensure_dataset
from workforce_intelligence.http import get_database
from workforce_intelligence.recruitment import OPEN_STATUSES, vacancy_snapshots
from workforce_intelligence.router import router
from workforce_intelligence.scale_seed import FULL_SEED
from workforce_intelligence.seed import INTERVIEW_SEED
from workforce_intelligence.vacancy_ageing import vacancy_ageing


@pytest.fixture(scope="module")
def full_dataset(tmp_path_factory):
    db = Database(tmp_path_factory.mktemp("ageing") / "workforce.sqlite3")
    ensure_dataset(db, FULL_SEED)
    return db


def test_all_five_age_bands_reconcile_to_canonical_open_snapshots(full_dataset):
    with full_dataset.transaction() as conn:
        state = current_dataset(conn)
        day = date.fromisoformat(state.as_of_date)
        report = vacancy_ageing(conn, day)
        open_records = [
            v for v in vacancy_snapshots(conn, state.as_of_date) if v.status in OPEN_STATUSES
        ]
        assert len(report.bands) == 5
        assert [b.code for b in report.bands] == ["0_30", "31_60", "61_90", "91_180", "181_plus"]
        assert report.total_open_requisitions == len(open_records)
        assert sum(b.requisitions for b in report.bands) == len(open_records)
        assert report.total_open_wte == pytest.approx(sum(v.open_wte for v in open_records))
        assert sum(b.open_wte for b in report.bands) == pytest.approx(report.total_open_wte)
        assert len(report.oldest_open) == min(12, len(open_records))
        assert report.oldest_open == sorted(
            report.oldest_open, key=lambda item: (-item.age_days, item.id)
        )
        metrics = {
            metric.definition.code: metric.current.value
            for metric in executive_metrics(conn, state, reporting_window(state, day, None)).metrics
        }
        assert metrics["open_vacancies"] == report.total_open_requisitions
        assert metrics["vacancy_wte"] == report.total_open_wte


def test_date_boundaries_and_closed_requests_are_excluded(tmp_path):
    db = Database(tmp_path / "workforce.sqlite3")
    ensure_dataset(db, INTERVIEW_SEED)
    with db.transaction() as conn:
        october = vacancy_ageing(conn, date(2026, 10, 31))
        assert october.total_open_requisitions == 3
        assert {row.id for row in october.oldest_open} == {"vac-003", "vac-004", "vac-006"}
        assert october.total_open_wte == pytest.approx(3.0)
        assert {b.code: b.requisitions for b in october.bands} == {
            "0_30": 2,
            "31_60": 0,
            "61_90": 1,
            "91_180": 0,
            "181_plus": 0,
        }
        prior = vacancy_ageing(conn, date(2026, 9, 30))
        assert any(row.id == "vac-002" for row in prior.oldest_open)
        assert all(row.id != "vac-002" for row in october.oldest_open)


def test_bucket_boundary_days_are_inclusive():
    from workforce_intelligence.vacancy_ageing import AGE_BANDS

    for boundary, expected in (
        (0, "0_30"),
        (30, "0_30"),
        (31, "31_60"),
        (60, "31_60"),
        (61, "61_90"),
        (90, "61_90"),
        (91, "91_180"),
        (180, "91_180"),
        (181, "181_plus"),
    ):
        matches = [
            code
            for code, _, minimum, maximum in AGE_BANDS
            if minimum <= boundary and (maximum is None or boundary <= maximum)
        ]
        assert matches == [expected]


def test_ageing_api_returns_revision_and_rejects_future_dates(tmp_path):
    db = Database(tmp_path / "workforce.sqlite3")
    seed = ensure_dataset(db, INTERVIEW_SEED)

    def member(request: Request) -> None:
        request.state.workforce_uid = "test-member"
        request.state.request_id = "req_ageing"

    app = FastAPI()
    app.include_router(router, prefix="/api", dependencies=[Depends(member)])
    app.dependency_overrides[get_database] = lambda: db
    with TestClient(app, base_url="https://backend.test/api/workforce/") as client:
        response = client.get("analytics/vacancy-ageing")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["dataset"]["revision"] == seed.revision
        assert body["synthetic"] is True
        assert body["ageing"]["total_open_requisitions"] == 3
        assert body["quality_status"] in ("passed", "review_required")
        assert (
            client.get("analytics/vacancy-ageing", params={"as_of_date": "2026-11-01"}).status_code
            == 422
        )


def test_ageing_includes_more_than_25_open_vacancies(tmp_path):
    """Verify ageing uses all open requisitions, not a UI-page-sized subset."""
    db = Database(tmp_path / "vacancy_ageing_pagination.sqlite3")
    ensure_dataset(db, INTERVIEW_SEED)
    cutoff = "2026-10-31"

    with db.transaction() as conn:
        baseline = len(
            [
                vacancy
                for vacancy in vacancy_snapshots(conn, cutoff)
                if vacancy.status in OPEN_STATUSES
            ]
        )

    with db.transaction(write=True) as conn:
        conn.executemany(
            """
            INSERT INTO vacancies (
                id, line_id, title,
                approved_positions, approved_fte_milli, approved_on
            ) VALUES (?, 'line-1', ?, 1, 1000, '2026-10-01')
            """,
            [(f"extra-{index:03d}", f"Synthetic vacancy {index}") for index in range(30)],
        )

    with db.transaction() as conn:
        report = vacancy_ageing(conn, date.fromisoformat(cutoff))
        open_records = [
            vacancy
            for vacancy in vacancy_snapshots(conn, cutoff)
            if vacancy.status in OPEN_STATUSES
        ]

        assert len(open_records) == baseline + 30
        assert len(open_records) > 25
        assert report.total_open_requisitions == len(open_records)
        assert sum(b.requisitions for b in report.bands) == len(open_records)
        assert report.total_open_wte == pytest.approx(
            sum(vacancy.open_wte for vacancy in open_records)
        )
        assert sum(b.open_wte for b in report.bands) == pytest.approx(report.total_open_wte)
        assert len(report.oldest_open) == 12
