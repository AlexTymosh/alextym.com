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
        event = connection.execute("SELECT * FROM audit_events").fetchone()
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
