from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from workforce_intelligence.database import Database
from workforce_intelligence.http import get_database
from workforce_intelligence.router import router


@pytest.fixture
def demo(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")

    def authorised_member(request: Request) -> None:
        request.state.workforce_uid = "test-member"
        request.state.request_id = "req_workforce_test"

    app = FastAPI()
    app.include_router(router, dependencies=[Depends(authorised_member)], prefix="/api")
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(app, base_url="https://backend.test/api/workforce/") as client:
        yield client, database


def executive(client, **query):
    response = client.get("analytics/executive", params=query)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["quality_status"] == "passed"
    assert data["synthetic"] is True
    return {
        metric["definition"]["code"]: metric["current"] for metric in data["executive"]["metrics"]
    }


def version(client):
    state = client.get("demo/status").json()["dataset"]
    return {key: state[key] for key in ("dataset_id", "dataset_generation")}


def source_command(client, action, expected_status=200, **fields):
    snapshot = client.get("demo/status").json()["dataset"]
    response = client.post(
        "operations",
        json={
            **{key: snapshot[key] for key in ("dataset_id", "dataset_generation", "revision")},
            "command": {"action": action, **fields},
        },
    )
    assert response.status_code == expected_status, response.text
    return response.json()


def test_planning_api_pins_revision_and_clears_saved_runs_on_reset(demo):
    client, database = demo
    state = client.get("demo/status").json()["dataset"]
    snapshot = {**version(client), "source_revision": state["revision"]}
    history = client.get("forecast/history", params={"metric": "vacancy_wte"})
    assert history.status_code == 200
    assert len(history.json()["history"]) == 4
    assert history.headers["cache-control"] == "no-store"
    request = {**snapshot, "metric": "vacancy_wte"}
    blocked = client.post("forecast", json={**request, "horizon": 13})
    assert blocked.status_code == 422
    assert client.post("forecast", json={**request, "source_revision": 10}).status_code == 409
    forecast = client.post("forecast", json=request)
    assert forecast.status_code == 200
    assert forecast.json()["forecast"]["status"] == "insufficient_history"
    assert client.post("forecast", json=request).json() == forecast.json()

    saved = client.post("scenarios", json={**snapshot, "inputs": {"approvals_per_month": 3}})
    assert saved.status_code == 200
    evaluation = saved.json()
    assert client.get(f"scenarios/{evaluation['run_id']}").json() == evaluation
    assert evaluation["evaluation"]["inputs"]["approvals_per_month"] == 3
    with database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM forecast_runs").fetchone()[0] == 2

    assert (
        client.post(
            "demo/reset",
            json={**version(client), "confirmed": True, "idempotency_key": str(uuid4())},
        ).status_code
        == 200
    )
    assert client.get(f"scenarios/{evaluation['run_id']}").status_code == 404
    assert client.post("forecast", json=request).status_code == 409
    with database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM forecast_runs").fetchone()[0] == 0


def test_architecture_examples_trace_the_same_contract_and_reconcile_to_gold(demo):
    client, _ = demo
    cutoff = "2026-10-15"
    response = client.get("architecture/layers", params={"as_of_date": cutoff})
    assert response.status_code == 200
    report = response.json()
    assert report["as_of_date"] == cutoff
    assert report["quality_status"] == "passed"
    sources = {layer["code"]: layer["values"] for layer in report["layers"]}
    assert sources["bronze"]["contract_id"] == sources["operational"]["contract_id"]
    assert sources["silver"]["employee_id"] == sources["operational"]["employee_id"]
    assert (
        sources["silver"]["contracted_fte_milli"] == sources["operational"]["contracted_fte_milli"]
    )
    assert sources["bronze"]["source_revision"] == report["dataset"]["revision"]
    gold = executive(client, as_of_date=cutoff)
    for code in ("budgeted_wte", "substantive_wte", "workforce_gap_wte"):
        assert sources["gold"][code] == gold[code]["value"]
    assert client.get("architecture/layers", params={"as_of_date": "2050-01-01"}).status_code == 422


def test_candidate_feedback_uses_an_application_cohort_and_rating_rules(demo):
    client, database = demo
    campaigns = client.get("surveys").json()["campaigns"]
    prepared = next(row for row in campaigns if row["survey_id"] == "candidate-feedback")
    assert prepared["audience"] == "candidates" and prepared["responses"] < prepared["invited"]
    with database.transaction() as connection:
        eligible = connection.execute(
            "SELECT COUNT(*) FROM fact_application WHERE received_on BETWEEN ? AND ?",
            (prepared["period_start"], prepared["period_end"]),
        ).fetchone()[0]
        assert prepared["eligible"] == eligible
    response = client.get(
        "surveys/candidate-feedback/analytics",
        params={
            "dimension": "organisation",
            "weight_by": "organisation",
            "theme": "candidate-communication",
        },
    )
    assert response.status_code == 200
    ratings = response.json()["report"]["ratings"]
    assert len(ratings) == 4
    assert ratings[0]["mean"] is not None
    assert ratings[-1]["answered"] is None or ratings[-1]["answered"] <= prepared["responses"]


def test_employment_workflow_preserves_contract_and_assignment_history(demo):
    client, _ = demo
    fields = dict(employee_id="demo-ops", contracted_fte="0.7")
    source_command(
        client,
        "add_employee",
        display_name="Demo Ops.",
        line_id="line-1",
        start_on="2026-08-01",
        **fields,
    )
    source_command(client, "edit_profile", employee_id="demo-ops", display_name="Demo Ops A.")
    source_command(
        client,
        "set_assignment",
        employee_id="demo-ops",
        effective_from="2026-09-01",
        line_id="line-2",
        kind="promotion",
    )
    source_command(
        client,
        "set_contract",
        employee_id="demo-ops",
        effective_from="2026-09-20",
        contracted_fte=0.9,
    )
    source_command(
        client,
        "record_learning",
        id="demo-training",
        employee_id="demo-ops",
        occurred_on="2026-10-02",
        activity_code="demo-safety",
    )
    source_command(
        client,
        "record_pdr",
        id="demo-pdr",
        employee_id="demo-ops",
        occurred_on="2026-10-08",
        status="completed",
    )
    source_command(
        client,
        "record_leaver",
        employee_id="demo-ops",
        leaving_date="2026-10-25",
        reason="resignation",
    )
    source_command(
        client,
        "set_contract",
        expected_status=422,
        employee_id="demo-ops",
        effective_from="2026-10-25",
        contracted_fte=1,
    )
    earlier = client.get("employees/demo-ops?as_of_date=2026-09-10").json()["employee"]
    current = client.get("employees/demo-ops").json()["employee"]
    assert earlier["employment_status"] == "Active"
    assert current["employment_status"] == "Leaver"
    assert [r["valid_to"] for r in current["contracts"]] == ["2026-10-25", "2026-09-20"]
    assert [r["line_id"] for r in current["assignments"]] == ["line-2", "line-1"]
    actions = {row["action"] for row in client.get("operations/audit").json()["items"]}
    assert {"promotion", "record_leaver", "record_pdr"}.issubset(actions)
    assert current["display_name"] == "Demo Ops A."
    assert client.delete("employees/demo-ops").status_code == 405


def test_full_recruitment_workflow_updates_gold_only_after_actual_start(demo):
    client, _ = demo
    baseline = executive(client)
    common = {"vacancy_id": "vac-ops"}
    source_command(
        client,
        "add_vacancy",
        title="Demo intake",
        line_id="line-2",
        requested_on="2026-10-05",
        approved_positions=1,
        approved_wte="0.8",
        **common,
    )
    assert executive(client)["open_vacancies"] == baseline["open_vacancies"]
    assert client.get("operations/vacancies").json()["next_offset"] is None
    source_command(
        client,
        "move_vacancy",
        expected_status=422,
        transition="publish",
        occurred_on="2026-10-06",
        **common,
    )
    source_command(client, "move_vacancy", transition="approve", occurred_on="2026-10-06", **common)
    source_command(client, "move_vacancy", transition="publish", occurred_on="2026-10-07", **common)
    app = {"application_id": "app-ops"}
    source_command(
        client, "add_application", received_on="2026-10-08", source_code="careers", **common, **app
    )
    source_command(
        client,
        "move_application",
        expected_status=422,
        transition="shortlisted",
        occurred_on="2026-10-09",
        **app,
    )
    source_command(
        client, "move_application", transition="screened", occurred_on="2026-10-09", **app
    )
    source_command(
        client, "move_application", transition="shortlisted", occurred_on="2026-10-10", **app
    )
    source_command(client, "record_interview", outcome="passed", occurred_on="2026-10-11", **app)
    source_command(client, "add_offer", id="offer-ops", offered_on="2026-10-12", **app)
    offer = {"offer_id": "offer-ops"}
    start = {"started_on": "2026-10-21", "contracted_fte": "0.8", **offer}
    source_command(client, "record_starter", expected_status=422, **start)
    source_command(client, "decide_offer", outcome="accepted", resolved_on="2026-10-13", **offer)
    source_command(client, "record_check", checked_on="2026-10-16", status="passed", **offer)
    source_command(
        client, "confirm_start", occurred_on="2026-10-17", planned_start_on="2026-10-21", **app
    )
    assert executive(client)["substantive_wte"] == baseline["substantive_wte"]
    source_command(client, "record_starter", **start)
    assert source_command(client, "record_starter", **start)["change"] == "unchanged"
    source_command(
        client,
        "record_probation",
        employee_id="starter-offer-ops",
        occurred_on="2026-10-30",
        outcome="passed",
    )
    assert executive(client)["substantive_wte"]["value"] == pytest.approx(
        baseline["substantive_wte"]["value"] + 0.8
    )
    state = client.get("operations/candidates").json()
    row = next(row for row in state["items"] if row["id"] == "app-ops")
    assert row["status"] == "probation_completed"


def test_explicit_establishment_override_and_stale_source_revision(demo):
    client, _ = demo
    start = client.get("demo/status").json()["dataset"]
    vacancy_id = "vac-exception"
    source_command(
        client,
        "add_vacancy",
        vacancy_id=vacancy_id,
        title="Demo oversized intake",
        line_id="line-1",
        requested_on="2026-10-20",
        approved_positions=10,
        approved_wte=10,
    )
    fields = dict(vacancy_id=vacancy_id, occurred_on="2026-10-22", transition="approve")
    source_command(client, "move_vacancy", expected_status=422, **fields)
    result = source_command(
        client, "move_vacancy", over_establishment_reason="Demo extra intake", **fields
    )
    assert result["dataset"]["revision"] == 2
    stale = client.post(
        "operations",
        json={
            "dataset_id": start["dataset_id"],
            "dataset_generation": 1,
            "revision": 0,
            "command": {
                "action": "add_campaign",
                "id": "demo-2026",
                "label": "Demo campaign",
                "opened_on": "2026-10-20",
            },
        },
    )
    assert stale.status_code == 409
    row = next(
        row for row in client.get("operations/vacancies").json()["items"] if row["id"] == vacancy_id
    )
    assert row["exception_reason"] == "Demo extra intake"


def test_generation_replacement_confirms_and_replays_only_the_same_intent(demo):
    client, _ = demo
    payload = {
        **version(client),
        "idempotency_key": str(uuid4()),
        "mode": "exploratory",
        "generation_seed": 99,
    }
    assert client.post("demo/seed", json={**payload, "confirmed": False}).status_code == 422
    result = client.post("demo/seed", json={**payload, "confirmed": True})
    assert result.status_code == 200, result.text
    assert result.json()["dataset"]["generation_seed"] == 99
    assert result.json()["dataset"]["scenario_code"] == "full-exploratory"
    assert client.post("demo/seed", json={**payload, "confirmed": True}).json()["replayed"]
    assert (
        client.post(
            "demo/seed", json={**payload, "confirmed": True, "generation_seed": 1}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "demo/reset",
            json={**version(client), "idempotency_key": str(uuid4()), "confirmed": True},
        ).status_code
        == 429
    )


def test_period_kpis_and_application_grain_reconcile(demo):
    client, _ = demo
    kpis = executive(client)
    assert kpis["budgeted_wte"]["value"] == 21
    assert kpis["open_vacancies"]["value"] == 3
    assert kpis["vacancy_wte"]["value"] == 3
    assert kpis["vacancy_rate"]["value"] == 14.29
    assert kpis["new_starters"]["value"] == 1
    assert kpis["median_time_to_hire"]["value"] == 15
    assert kpis["offer_acceptance_rate"] == {
        "value": 33.33,
        "numerator": 1,
        "denominator": 3,
        "sample_size": None,
        "status": "available",
        "reason": None,
    }

    result = client.get("analytics/candidate-funnel").json()["funnel"]
    assert result["grain"] == "distinct_application"
    counts = {stage["stage"]: stage["application_count"] for stage in result["stages"]}
    assert (counts["received"], counts["screened"], counts["started"]) == (5, 4, 0)
    assert result["application_to_start"]["denominator"] == 5
    filtered = client.get("analytics/candidate-funnel", params={"vacancy_id": "vac-003"}).json()[
        "funnel"
    ]
    assert filtered["stages"][0]["application_count"] == 2
    assert filtered["stages"][1]["application_count"] == 2  # repeated screening is one reach
    assert filtered["stages"][5]["application_count"] == 1
    assert filtered["stages"][8]["application_count"] == 0


def test_effective_edit_refreshes_gold_and_keeps_dates_and_audit(demo):
    client, database = demo
    full = client.get("employees", params={"limit": 15}).json()
    assert [person["display_name"] for person in full["items"]] == [
        f"Demo {c}." for c in "ABCDEFGHIJKLMNO"
    ]
    assert full["next_offset"] == 15
    before = executive(client)["workforce_gap_wte"]["value"]
    historical = executive(client, as_of_date="2026-10-19")["workforce_gap_wte"]["value"]
    change = {
        **version(client),
        "record_version": 1,
        "contracted_fte": 0.8,
        "effective_from": "2026-10-20",
    }
    response = client.patch("employees/emp-001/contracts", json=change)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["record_version"] == 2
    assert response.json()["dataset"]["revision"] == 1
    assert executive(client)["workforce_gap_wte"]["value"] == pytest.approx(before + 0.2)
    assert executive(client, as_of_date="2026-10-19")["workforce_gap_wte"]["value"] == historical
    assert client.patch("employees/emp-001/contracts", json=change).status_code == 409
    with database.transaction() as connection:
        event = connection.execute(
            "SELECT * FROM audit_events WHERE action = 'change_fte'"
        ).fetchone()
        assert (event["actor_uid"], event["correlation_id"], event["action"]) == (
            "test-member",
            "req_workforce_test",
            "change_fte",
        )


def test_cancel_and_actual_start_have_different_workforce_effects(demo):
    client, _ = demo
    base = executive(client)
    epoch = version(client)
    response = client.post(
        "vacancies/vac-006/cancel",
        json={**epoch, "record_version": 1, "cancelled_on": "2026-10-28"},
    )
    assert response.status_code == 200, response.text
    cancelled = executive(client)
    assert cancelled["open_vacancies"]["value"] == 2
    assert cancelled["vacancy_wte"]["value"] == 2
    assert cancelled["workforce_gap_wte"]["value"] == base["workforce_gap_wte"]["value"]
    assert cancelled["new_starters"]["value"] == base["new_starters"]["value"]
    rows = client.get("analytics/vacancy-lifecycle").json()
    assert rows["status_counts"] == {
        "cancelled": 2,
        "advertised": 1,
        "partially_filled": 1,
        "closed": 1,
        "filled": 1,
    }
    current_vacancy = {row["id"]: row for row in rows["items"]}
    assert current_vacancy["vac-006"]["filled_wte"] == 0
    assert current_vacancy["vac-004"]["filled_wte"] == 0.8
    assert current_vacancy["vac-004"]["open_wte"] == 1

    starter = {**epoch, "record_version": 1, "started_on": "2026-10-29", "contracted_fte": 1}
    assert client.post("starters", json={**starter, "offer_id": "offer-003"}).status_code == 422
    assert (
        client.post(
            "starters", json={**starter, "offer_id": "offer-002", "started_on": "2026-10-20"}
        ).status_code
        == 422
    )
    response = client.post("starters", json={**starter, "offer_id": "offer-002"})
    assert response.status_code == 201, response.text
    assert response.json()["record_version"] == 2
    assert client.post("starters", json={**starter, "offer_id": "offer-002"}).status_code == 409
    filled = executive(client)
    assert filled["workforce_gap_wte"]["value"] == pytest.approx(
        base["workforce_gap_wte"]["value"] - 1
    )
    assert filled["new_starters"]["value"] == 2
    funnel = client.get("analytics/candidate-funnel").json()["funnel"]
    assert funnel["application_to_start"]["value"] == 20
    assert funnel["application_to_start"]["denominator"] == 5


def test_empty_denominators_reset_replay_and_stale_tab(demo):
    client, _ = demo
    reset_api = client.app.openapi()["paths"]["/api/workforce/demo/reset"]["post"]
    assert reset_api["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorDetail",
    }
    early = executive(client, as_of_date="2026-07-30")
    assert early["offer_acceptance_rate"]["value"] is None
    assert early["offer_acceptance_rate"]["status"] == "unavailable"
    assert early["new_starters"]["value"] == 0
    latest_day = client.get(
        "analytics/candidate-funnel",
        params={"as_of_date": "2026-10-08", "period_start": "2026-10-08"},
    ).json()["funnel"]["application_to_start"]
    assert latest_day["denominator"] == 1
    assert latest_day["status"] == "unavailable"
    assert client.get("analytics/executive", params={"as_of_date": "2026-12-01"}).status_code == 422
    epoch = version(client)
    body = {**epoch, "idempotency_key": str(uuid4())}
    assert client.post("demo/reset", json={**body, "confirmed": False}).status_code == 422
    reset = client.post("demo/reset", json={**body, "confirmed": True})
    assert reset.status_code == 200, reset.text
    assert reset.json()["reset_generation"] == 2
    retry = client.post("demo/reset", json={**body, "confirmed": True})
    assert retry.json()["replayed"] is True
    current = client.post(
        "demo/reset", json={**version(client), "confirmed": True, "idempotency_key": str(uuid4())}
    )
    assert current.status_code == 429
    assert int(current.headers["retry-after"]) > 0
    stale = client.patch(
        "employees/emp-001/contracts",
        json={**epoch, "record_version": 1, "contracted_fte": 0.8, "effective_from": "2026-10-20"},
    )
    assert stale.status_code == 409
    assert stale.headers["cache-control"] == "no-store"


def test_reviewed_report_reproduces_after_reset_and_excludes_draft_from_gold(demo):
    client, database = demo
    response = client.get("surveys/reports/rota-pressure")
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    assert report["analysis_label"] == "Demonstration fallback result"
    assert report["total_responses"] == 12
    assert report["analysable_responses"] == 10
    assert [finding["id"] for finding in report["findings"]] == ["signal-rota-001"]
    assert [draft["id"] for draft in report["drafts"]] == ["signal-rota-002"]
    finding = report["findings"][0]
    assert finding["prevalence"] == 60
    assert len({evidence["response_id"] for evidence in finding["evidence"]}) == 6
    assert finding["review_kind"] == "Seeded demonstration review"
    assert report["actions"][0]["signal_id"] == finding["id"]
    assert (
        client.post(
            "demo/reset",
            json={**version(client), "confirmed": True, "idempotency_key": str(uuid4())},
        ).status_code
        == 200
    )
    assert client.get("surveys/reports/rota-pressure").json()["report"] == report
    with database.transaction() as connection:
        audits = connection.execute("SELECT action FROM audit_events ORDER BY id").fetchall()
        assert [row[0] for row in audits] == ["publish_seeded_fallback", "reset"]


def test_insight_pilot_uses_governed_result_for_selected_dates(demo):
    client, _ = demo
    query = {
        "intent": "explain_vacancy_rate",
        "as_of_date": "2026-10-12",
        "period_start": "2026-10-01",
    }
    insight = client.post("insight-pilot/query", json=query)
    assert insight.status_code == 200, insight.text
    answer = insight.json()
    assert (
        answer["metric"]["current"]
        == executive(client, as_of_date=query["as_of_date"], period_start=query["period_start"])[
            "vacancy_rate"
        ]
    )
    assert answer["window"] == {"start": query["period_start"], "end": query["as_of_date"]}
    assert answer["report_section"] == "executive"
    assert (
        client.post(
            "insight-pilot/query", json={**query, "sql": "SELECT * FROM employees"}
        ).status_code
        == 422
    )
    assert client.post("insight-pilot/query", json={**query, "intent": "other"}).status_code == 422
