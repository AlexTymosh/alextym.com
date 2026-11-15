"""Disclosure-safe inclusive recruitment: cohort, complement and API tests."""

import json
import sqlite3

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from workforce_intelligence.database import Database
from workforce_intelligence.dataset import current_dataset, ensure_dataset
from workforce_intelligence.http import get_database
from workforce_intelligence.inclusive_recruitment import CATEGORIES, inclusive_recruitment
from workforce_intelligence.router import router
from workforce_intelligence.scale_seed import FULL_SEED
from workforce_intelligence.seed import INTERVIEW_SEED


def _fixture() -> sqlite3.Connection:
    """Independent minimal event-grain fixture, without a project seed."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE fact_application (id TEXT PRIMARY KEY, received_on TEXT NOT NULL);
        CREATE TABLE candidate_demographics (
          application_id TEXT PRIMARY KEY, age_band TEXT, ethnicity_group TEXT, disability_status TEXT
        );
        CREATE TABLE fact_application_stage_event (application_id TEXT, stage_code TEXT, occurred_on TEXT);
        CREATE TABLE fact_offer (application_id TEXT, outcome TEXT, offered_on TEXT, resolved_on TEXT);
        CREATE TABLE fact_new_starter (application_id TEXT, started_on TEXT);
        """
    )
    connection.executemany(
        "INSERT INTO fact_application VALUES (?, '2026-08-01')",
        [(f"app-{i:03d}",) for i in range(20)],
    )
    return connection


def _dimension(report, code: str):
    return next(dimension for dimension in report.dimensions if dimension.code == code)


def _assert_masked(dimension):
    assert dimension.status == "suppressed"
    assert dimension.message.startswith("Suppressed:")
    for group in dimension.groups:
        assert group.applications is None
        assert group.shortlisted is None
        assert group.interviewed is None
        assert group.accepted_offers is None
        assert group.starters is None
        assert group.representation_percent is None
        assert group.appointment_percent is None


def test_eligible_complete_cohort_can_be_published():
    conn = _fixture()
    report = inclusive_recruitment(conn, as_of_date="2026-10-31")
    assert report.scope == "all_observed_applications"
    assert report.threshold == 5
    assert {d.code for d in report.dimensions} == set(CATEGORIES)
    for dimension in report.dimensions:
        assert dimension.status == "available"
        assert sum(group.applications for group in dimension.groups) == 20
        declared = next(group for group in dimension.groups if group.code == "not-stated")
        assert declared.applications == 20
        assert declared.representation_percent == 100
        assert declared.appointment_percent == 0


def test_one_small_group_suppresses_full_dimension_to_block_complements():
    conn = _fixture()
    conn.execute("INSERT INTO candidate_demographics VALUES ('app-000', '18-24', 'white', 'yes')")
    report = inclusive_recruitment(conn, as_of_date="2026-10-31")
    for dimension in report.dimensions:
        _assert_masked(dimension)
    # Never publish another group's 19 and allow a global 20 to reveal the hidden 1.
    assert json.dumps(report.__dict__, default=lambda value: value.__dict__).count("app-000") == 0


def test_small_stage_and_its_complement_also_suppress():
    conn = _fixture()
    # Twenty applications, two shortlists -> small numerator and complement.
    conn.executemany(
        "INSERT INTO fact_application_stage_event VALUES (?, 'shortlisted', '2026-08-05')",
        [("app-000",), ("app-001",)],
    )
    report = inclusive_recruitment(conn, as_of_date="2026-10-31")
    _assert_masked(_dimension(report, "ethnicity_group"))

    conn.execute("DELETE FROM fact_application_stage_event")
    # A safe shortlist count (18) still reveals two failures from denominator 20.
    conn.executemany(
        "INSERT INTO fact_application_stage_event VALUES (?, 'shortlisted', '2026-08-05')",
        [(f"app-{i:03d}",) for i in range(18)],
    )
    _assert_masked(_dimension(inclusive_recruitment(conn, as_of_date="2026-10-31"), "age_band"))


def test_repeated_stage_events_count_each_application_once():
    conn = _fixture()
    conn.executemany(
        "INSERT INTO fact_application_stage_event VALUES (?, 'screened', '2026-08-05')",
        [(f"app-{i:03d}",) for i in range(20)] * 2,
    )
    dimension = _dimension(inclusive_recruitment(conn, as_of_date="2026-10-31"), "age_band")
    assert dimension.status == "available"
    assert next(group for group in dimension.groups if group.code == "not-stated").screened == 20


def test_unknown_demographic_codes_are_normalised_to_not_stated():
    conn = _fixture()
    conn.executemany(
        "INSERT INTO candidate_demographics VALUES (?, 'unexpected', 'white', 'no')",
        [(f"app-{i:03d}",) for i in range(20)],
    )
    dimension = _dimension(inclusive_recruitment(conn, as_of_date="2026-10-31"), "age_band")
    assert dimension.status == "available"
    assert (
        next(group for group in dimension.groups if group.code == "not-stated").applications == 20
    )
    assert all(group.code != "unexpected" for group in dimension.groups)


def test_empty_cohort_is_unavailable_not_zero():
    conn = _fixture()
    report = inclusive_recruitment(conn, as_of_date="2026-01-01")
    assert all(d.status == "unavailable" for d in report.dimensions)
    assert all(g.applications is None for d in report.dimensions for g in d.groups)


@pytest.fixture(scope="module")
def full_dataset(tmp_path_factory):
    db = Database(tmp_path_factory.mktemp("inclusive") / "workforce.sqlite3")
    ensure_dataset(db, FULL_SEED)
    return db


def test_full_seed_has_fixed_categories_and_no_raw_identifiers(full_dataset):
    with full_dataset.transaction() as conn:
        state = current_dataset(conn)
        report = inclusive_recruitment(conn, as_of_date=state.as_of_date)
        assert report.as_of_date == state.as_of_date
        assert len(report.dimensions) == 3
        for dimension in report.dimensions:
            assert [group.code for group in dimension.groups] == list(CATEGORIES[dimension.code])
            if dimension.status == "available":
                count = conn.execute(
                    "SELECT COUNT(*) FROM fact_application WHERE received_on <= ?",
                    (state.as_of_date,),
                ).fetchone()[0]
                assert sum(group.applications for group in dimension.groups) == count
            else:
                _assert_masked(dimension)


def test_mutable_revision_revokes_all_inclusive_counts(tmp_path):
    """A small edit must not be recoverable by comparing two API revisions."""
    from workforce_intelligence.dataset import advance_revision

    db = Database(tmp_path / "mutable-disclosure.sqlite3")
    ensure_dataset(db, FULL_SEED)

    def member(request: Request) -> None:
        request.state.workforce_uid = "test-member"
        request.state.request_id = "req_privacy"

    app = FastAPI()
    app.include_router(router, prefix="/api", dependencies=[Depends(member)])
    app.dependency_overrides[get_database] = lambda: db
    with TestClient(app, base_url="https://backend.test/api/workforce/") as client:
        before = client.get("analytics/inclusive-recruitment")
        assert before.status_code == 200
        original = before.json()
        assert len(original["report"]["dimensions"]) == len(CATEGORIES)

        with db.transaction(write=True) as conn:
            advance_revision(conn, current_dataset(conn))

        after = client.get("analytics/inclusive-recruitment")
        assert after.status_code == 200
        revised = after.json()
        assert revised["dataset"]["revision"] == original["dataset"]["revision"] + 1
        for dimension in revised["report"]["dimensions"]:
            assert dimension["status"] == "suppressed"
            assert "Suppressed:" in dimension["message"]
            for group in dimension["groups"]:
                assert all(value is None for key, value in group.items() if key != "code")


def test_exploratory_generation_never_publishes_inclusive_cells(tmp_path):
    """Changing the generation seed cannot create a differencing oracle."""
    from dataclasses import replace

    db = Database(tmp_path / "exploratory-disclosure.sqlite3")
    ensure_dataset(db, replace(FULL_SEED, scenario_code="full-exploratory", generation_seed=424401))

    def member(request: Request) -> None:
        request.state.workforce_uid = "test-member"
        request.state.request_id = "req_exploratory"

    app = FastAPI()
    app.include_router(router, prefix="/api", dependencies=[Depends(member)])
    app.dependency_overrides[get_database] = lambda: db
    with TestClient(app, base_url="https://backend.test/api/workforce/") as client:
        result = client.get("analytics/inclusive-recruitment")
        assert result.status_code == 200
        for dimension in result.json()["report"]["dimensions"]:
            assert dimension["status"] == "suppressed"
            assert all(
                value is None
                for group in dimension["groups"]
                for key, value in group.items()
                if key != "code"
            )


def test_gate_clears_every_metric_and_retains_only_public_codes():
    conn = _fixture()
    report = inclusive_recruitment(conn, as_of_date="2026-10-31")
    from workforce_intelligence.inclusive_recruitment import suppress_inclusive_report

    masked = suppress_inclusive_report(report, "Suppressed: changed revision")
    assert masked.scope == report.scope
    assert masked.threshold == report.threshold
    assert all(d.status == "suppressed" for d in masked.dimensions)
    assert all(
        value is None
        for dimension in masked.dimensions
        for group in dimension.groups
        for key, value in vars(group).items()
        if key != "code"
    )


def test_api_rejects_filter_inference_and_never_returns_raw_candidates(tmp_path):
    db = Database(tmp_path / "inclusive.sqlite3")
    ensure_dataset(db, INTERVIEW_SEED)

    def member(request: Request) -> None:
        request.state.workforce_uid = "test-member"
        request.state.request_id = "req_inclusive"

    app = FastAPI()
    app.include_router(router, prefix="/api", dependencies=[Depends(member)])
    app.dependency_overrides[get_database] = lambda: db
    with TestClient(app, base_url="https://backend.test/api/workforce/") as client:
        response = client.get("analytics/inclusive-recruitment")
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["synthetic"] is True
        assert result["report"]["scope"] == "all_observed_applications"
        for dimension in result["report"]["dimensions"]:
            assert dimension["status"] in ("available", "suppressed", "unavailable")
            for group in dimension["groups"]:
                assert set(group) == {
                    "code",
                    "applications",
                    "screened",
                    "shortlisted",
                    "interviewed",
                    "offers_made",
                    "accepted_offers",
                    "starters",
                    "representation_percent",
                    "shortlisting_percent",
                    "interview_percent",
                    "offer_acceptance_percent",
                    "appointment_percent",
                }
        for query in (
            "as_of_date=2026-10-01",
            "period_start=2026-07-01",
            "vacancy_id=vac-001",
            "organisation_id=response",
            "ethnicity_group=white",
            "as_of_date=2026-10-31&as_of_date=2026-10-30",
        ):
            assert client.get(f"analytics/inclusive-recruitment?{query}").status_code == 422
        for forbidden in ("app-001", "emp-001", "application_id", "candidate_id"):
            assert forbidden not in response.text
