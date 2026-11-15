from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from workforce_intelligence import workbook_import
from workforce_intelligence.database import Database
from workforce_intelligence.dataset import (
    AuditActor,
    Conflict,
    InvalidOperation,
    current_dataset,
    ensure_dataset,
    reset_dataset,
)
from workforce_intelligence.http import get_database
from workforce_intelligence.router import router
from workforce_intelligence.seed import INTERVIEW_SEED
from workforce_intelligence.workbook_import import (
    ImportConfirmation,
    commit_import,
    preview_import,
)
from workforce_intelligence.workbook_model import (
    MAX_UPLOAD_BYTES,
    SHEETS,
    XLSX_TYPE,
    columns_for,
)
from workforce_intelligence.xlsx import (
    INFO_SHEET,
    book_bytes,
    new_book,
    parse_xlsx,
    tab,
    template,
)

ACTOR = AuditActor("test-member", "req_workbook")


def workbook(*rows):
    book = load_workbook(BytesIO(template()))
    for sheet, values in rows:
        book[sheet].append([values.get(column) for column in columns_for(sheet)])
    return book_bytes(book)


PERSON = (
    "Employees",
    {
        "action": "add_employee",
        "employee_id": "demo-excel",
        "display_name": "Demo EX.",
        "line_id": "line-1",
        "start_on": "2026-10-03",
        "contracted_fte": 0.8,
    },
)
CONTRACT = (
    "Contracts",
    {
        "action": "set_contract",
        "employee_id": "demo-excel",
        "effective_from": "2026-10-03",
        "contracted_fte": 0.9,
    },
)


@pytest.fixture
def running(tmp_path):
    database = Database(tmp_path / "workforce.sqlite3")
    app = FastAPI()

    def identify(request: Request):
        if identity := request.headers.get("x-test-member"):
            request.state.workforce_uid = identity
            request.state.request_id = ACTOR.correlation_id

    app.include_router(router, prefix="/api", dependencies=[Depends(identify)])
    app.dependency_overrides[get_database] = lambda: database
    with TestClient(
        app,
        base_url="https://localhost/api/workforce/",
        headers={"x-test-member": ACTOR.uid},
    ) as client:
        yield client, database


def payload(preview):
    state = preview.dataset
    return ImportConfirmation(
        confirmed=True,
        batch_id=preview.batch_id,
        dataset_id=state.dataset_id,
        dataset_generation=state.dataset_generation,
    )


def validate(client, data):
    return client.post("import/validate", content=data, headers={"content-type": XLSX_TYPE})


def test_excel_preview_only_stages_and_commit_is_atomic_and_idempotent(running):
    client, database = running
    data = workbook(PERSON, CONTRACT)
    asset = client.get("import/template")
    assert asset.status_code == 200 and asset.headers["cache-control"] == "no-store"
    assert asset.headers["content-type"] == XLSX_TYPE
    audits_before = client.get("operations/audit").json()["items"]
    with BytesIO(asset.content) as stream:
        book = load_workbook(stream, read_only=True)
        assert book.sheetnames == [INFO_SHEET, *SHEETS]
        book.close()
    response = validate(client, data)
    assert response.status_code == 200, response.text
    preview = workbook_import.ImportPreview.model_validate(response.json())
    assert preview.counts.model_dump() == {
        "insert": 1,
        "update": 1,
        "unchanged": 0,
        "invalid": 0,
        "warnings": 0,
    }
    assert validate(client, data).json()["batch_id"] == str(preview.batch_id)
    metric = next(row for row in preview.impact if row.metric == "substantive_wte")
    assert metric.after == pytest.approx(metric.before + 0.9)
    assert client.get("employees/demo-excel").status_code == 404
    assert client.get("operations/audit").json()["items"] == audits_before
    confirmation = payload(preview).model_dump(mode="json")
    assert (
        client.post("import/commit", json={**confirmation, "confirmed": False}).status_code == 422
    )
    result = client.post("import/commit", json=confirmation)
    assert result.status_code == 200, result.text
    assert result.json()["dataset"]["revision"] == preview.dataset.revision + 1
    row = client.get("employees/demo-excel").json()["employee"]
    assert row["contracts"][0]["contracted_fte"] == 0.9
    assert client.post("import/commit", json=confirmation).json()["replayed"] is True
    with database.transaction() as conn:
        assert [
            tuple(row)
            for row in conn.execute(
                "SELECT source_channel, action FROM audit_events WHERE source_channel = 'excel' ORDER BY id"
            )
        ] == [
            ("excel", "add_employee"),
            ("excel", "set_contract"),
            ("excel", "confirm_import"),
        ]


def test_invalid_rows_abort_commit_and_report_precise_locations(running):
    client, _ = running
    response = validate(
        client,
        workbook(
            PERSON,
            (
                "Employees",
                {**PERSON[1], "employee_id": "invalid-line", "line_id": "missing"},
            ),
            ("Contracts", {**CONTRACT[1], "contracted_fte": "=SUM(1,1)"}),
            ("Contracts", {**CONTRACT[1], "effective_from": "31/10/2026"}),
        ),
    )
    assert response.status_code == 200, response.text
    preview = workbook_import.ImportPreview.model_validate(response.json())
    assert preview.counts.invalid == 3
    assert [(r.sheet, r.row) for r in preview.rows if r.result == "invalid"] == [
        ("Employees", 3),
        ("Contracts", 2),
        ("Contracts", 3),
    ]
    assert preview.impact == []
    batch = preview.batch_id
    assert (
        client.post("import/commit", json=payload(preview).model_dump(mode="json")).status_code
        == 422
    )
    assert client.get("employees/demo-excel").status_code == 404
    errors = client.get(f"import/{batch}/errors")
    with BytesIO(errors.content) as stream:
        book = load_workbook(stream, read_only=True)
        assert list(book["Validation issues"].values)[1][0:2] == ("Employees", 3)
        assert len(list(book["Validation issues"].values)) == 4
        book.close()
    outsider = {"x-test-member": "another-member"}
    assert client.get(f"import/{batch}/errors", headers=outsider).status_code == 404
    assert (
        client.post(
            "import/commit",
            json=payload(preview).model_dump(mode="json"),
            headers=outsider,
        ).status_code
        == 404
    )


def test_uploaded_reference_and_survey_rows_share_validation_without_moving_published_evidence(
    running,
):
    client, _ = running
    response = validate(
        client,
        workbook(
            (
                "ReferenceData",
                {
                    "action": "set_reference",
                    "kind": "location",
                    "id": "central",
                    "label": "Demo Central Hub",
                    "active": True,
                },
            ),
            (
                "SurveyResponses",
                {
                    "action": "add_survey_campaign",
                    "survey_id": "demo-import-survey",
                    "title": "Demo imported pulse",
                    "period_start": "2026-10-03",
                    "period_end": "2026-10-29",
                    "invited": 12,
                },
            ),
            (
                "SurveyResponses",
                {
                    "action": "record_survey_response",
                    "id": "demo-answer",
                    "survey_id": "demo-import-survey",
                    "submitted_on": "2026-10-15",
                    "comment_code": "rota_pressure",
                },
            ),
        ),
    )
    assert response.status_code == 200, response.text
    preview = workbook_import.ImportPreview.model_validate(response.json())
    assert (
        preview.counts.insert == 2
        and preview.counts.unchanged == 1
        and preview.counts.warnings == 1
    )
    assert (
        client.post("import/commit", json=payload(preview).model_dump(mode="json")).status_code
        == 200
    )
    reviewed = client.get("surveys/reports/rota-pressure").json()["report"]["survey_id"]
    protected = validate(
        client,
        workbook(
            (
                "SurveyResponses",
                {
                    "action": "record_survey_response",
                    "id": "demo-no-overwrite",
                    "survey_id": reviewed,
                    "submitted_on": "2026-10-15",
                    "comment_code": "positive",
                },
            ),
        ),
    ).json()
    assert protected["counts"]["invalid"] == 1


def test_failed_commit_rolls_back_rows_and_leaves_batch_recoverable(tmp_path, monkeypatch):
    database = Database(tmp_path / "test.sqlite3")
    initial = ensure_dataset(database, INTERVIEW_SEED)
    preview = preview_import(database, ACTOR, workbook(PERSON, CONTRACT))
    original = workbook_import._apply

    def interrupted(editor, command):
        if command.action == "set_contract":
            raise InvalidOperation("unexpected commit-time constraint")
        return original(editor, command)

    with monkeypatch.context() as patch:
        patch.setattr(workbook_import, "_apply", interrupted)
        with pytest.raises(Conflict, match="rolled back"):
            commit_import(database, ACTOR, payload(preview))
    with database.transaction() as conn:
        assert current_dataset(conn) == initial
        assert not conn.execute("SELECT 1 FROM employees WHERE id = 'demo-excel'").fetchone()
        assert not conn.execute(
            "SELECT 1 FROM audit_events WHERE source_channel = 'excel'"
        ).fetchone()
        failed = conn.execute("SELECT last_failure_at, receipt_json FROM import_batches").fetchone()
        assert failed["last_failure_at"] and failed["receipt_json"] is None
    assert commit_import(database, ACTOR, payload(preview)).dataset.revision == 1


def test_reset_and_confirmation_serialize_and_invalidate_old_preview(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    state = ensure_dataset(database, INTERVIEW_SEED)
    preview = preview_import(database, ACTOR, workbook(PERSON))
    with ThreadPoolExecutor(max_workers=2) as pool:
        importing = pool.submit(commit_import, database, ACTOR, payload(preview))
        resetting = pool.submit(
            reset_dataset,
            database,
            INTERVIEW_SEED,
            expected=state,
            actor=ACTOR,
            idempotency_key="reset",
        )
        assert (
            resetting.result(timeout=6).dataset.dataset_generation == state.dataset_generation + 1
        )
        try:
            importing.result(timeout=6)
        except Conflict as failure:
            assert "dataset changed" in str(failure)
    with pytest.raises(Conflict, match="dataset changed"):
        commit_import(database, ACTOR, payload(preview))
    with database.transaction() as conn:
        assert not conn.execute("SELECT 1 FROM employees WHERE id = 'demo-excel'").fetchone()
        assert not conn.execute("SELECT 1 FROM import_batches").fetchone()


def test_workbook_limits_authentication_and_invalid_archives(running):
    client, database = running
    missing = client.post(
        "import/validate",
        content=b"bad workbook",
        headers={
            "x-test-member": "",
            "content-type": XLSX_TYPE,
        },
    )
    assert missing.status_code == 401
    assert not database.path.exists()
    assert validate(client, b"x" * (MAX_UPLOAD_BYTES + 1)).status_code == 413
    assert client.post("import/validate", content=b"not xlsx").status_code == 415
    assert validate(client, b"not xlsx").status_code == 422
    dense = load_workbook(BytesIO(template()))
    dense["Employees"].cell(503, 1, "add_employee")
    assert validate(client, book_bytes(dense)).status_code == 422
    dtd = BytesIO()
    with (
        ZipFile(BytesIO(template())) as source,
        ZipFile(dtd, "w", ZIP_DEFLATED) as destination,
    ):
        for name in source.namelist():
            raw = source.read(name)
            if name == "xl/workbook.xml":
                raw = b"<!DOCTYPE workbook [<!ENTITY test 'not allowed'>]>" + raw
            destination.writestr(name, raw)
    assert validate(client, dtd.getvalue()).status_code == 422
    assert (
        validate(client, workbook(*[(PERSON[0], PERSON[1])] * 2)).json()["counts"]["invalid"] == 1
    )
    throttled = validate(client, workbook(PERSON))
    assert throttled.status_code == 429 and throttled.headers["retry-after"] == "60"


def test_filtered_exports_are_synthetic_and_formula_safe(running):
    client, _ = running
    response = client.post(
        "export",
        json={
            "kind": "analytics",
            "as_of_date": "2026-10-31",
            "period_start": "2026-10-01",
            "vacancy_id": "vac-006",
        },
    )
    assert response.status_code == 200, response.text
    book = load_workbook(BytesIO(response.content), read_only=True)
    assert "Synthetic demonstration data" in book[INFO_SHEET]["B2"].value
    assert list(book["Application funnel"].values)[1][1] == 2
    book.close()
    survey = client.post("export", json={"kind": "survey"})
    book = load_workbook(BytesIO(survey.content), read_only=True)
    assert len(list(book["Published findings"].values)) == 2
    assert len(list(book["Permitted evidence"].values)) == 7
    book.close()
    synthetic = new_book("Formula safety check")
    tab(synthetic, "Test", ("Value",), (("=SUM(1,1)",), (" +CMD",), ("\tcommand",)))
    downloaded = load_workbook(BytesIO(book_bytes(synthetic)))
    assert [(c.value, c.data_type) for c in downloaded["Test"]["A"][1:]] == [
        ("'=SUM(1,1)", "s"),
        ("' +CMD", "s"),
        ("'\tcommand", "s"),
    ]
    downloaded.close()


def test_excess_uncompressed_workbook_payload_is_rejected():
    target = BytesIO()
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", b"A" * (3 * 1024 * 1024))
    with pytest.raises(InvalidOperation, match="without embedded files"):
        parse_xlsx(target.getvalue())


def test_closed_vacancy_workbook_backfill_preserves_historical_recruitment(running):
    """Vacancies are imported before Applications; old events must remain importable."""
    client, database = running
    vacancy = "vac-workbook-closed"
    application = "app-workbook-closed"
    offer = "offer-workbook-closed"
    payload_bytes = workbook(
        (
            "Vacancies",
            {
                "action": "add_vacancy",
                "vacancy_id": vacancy,
                "line_id": "line-2",
                "title": "Demo historical intake",
                "requested_on": "2026-10-05",
                "approved_positions": 1,
                "approved_wte": 0.8,
            },
        ),
        (
            "Vacancies",
            {
                "action": "move_vacancy",
                "vacancy_id": vacancy,
                "transition": "approve",
                "occurred_on": "2026-10-06",
            },
        ),
        (
            "Vacancies",
            {
                "action": "move_vacancy",
                "vacancy_id": vacancy,
                "transition": "publish",
                "occurred_on": "2026-10-07",
            },
        ),
        (
            "Vacancies",
            {
                "action": "move_vacancy",
                "vacancy_id": vacancy,
                "transition": "close",
                "occurred_on": "2026-10-27",
            },
        ),
        (
            "Applications",
            {
                "action": "add_application",
                "application_id": application,
                "vacancy_id": vacancy,
                "received_on": "2026-10-08",
                "source_code": "careers",
            },
        ),
        (
            "Applications",
            {
                "action": "move_application",
                "application_id": application,
                "transition": "screened",
                "occurred_on": "2026-10-09",
            },
        ),
        (
            "Applications",
            {
                "action": "move_application",
                "application_id": application,
                "transition": "shortlisted",
                "occurred_on": "2026-10-10",
            },
        ),
        (
            "Applications",
            {
                "action": "record_interview",
                "application_id": application,
                "occurred_on": "2026-10-11",
                "outcome": "passed",
            },
        ),
        (
            "Offers",
            {
                "action": "add_offer",
                "id": offer,
                "application_id": application,
                "offered_on": "2026-10-12",
            },
        ),
        (
            "Offers",
            {
                "action": "decide_offer",
                "offer_id": offer,
                "resolved_on": "2026-10-13",
                "outcome": "accepted",
            },
        ),
        (
            "PreEmploymentChecks",
            {
                "action": "record_check",
                "offer_id": offer,
                "checked_on": "2026-10-16",
                "status": "passed",
            },
        ),
        (
            "NewStarters",
            {
                "action": "confirm_start",
                "application_id": application,
                "occurred_on": "2026-10-17",
                "planned_start_on": "2026-10-21",
            },
        ),
        (
            "NewStarters",
            {
                "action": "record_starter",
                "offer_id": offer,
                "started_on": "2026-10-21",
                "contracted_fte": 0.8,
            },
        ),
    )

    response = validate(client, payload_bytes)
    assert response.status_code == 200, response.text
    preview = workbook_import.ImportPreview.model_validate(response.json())
    assert preview.counts.invalid == 0, [
        (row.sheet, row.row, row.message) for row in preview.rows if row.result == "invalid"
    ]
    assert client.get(f"employees/starter-{offer}").status_code == 404
    committed = client.post("import/commit", json=payload(preview).model_dump(mode="json"))
    assert committed.status_code == 200, committed.text
    assert client.get(f"employees/starter-{offer}").status_code == 200
    with database.transaction() as conn:
        row = conn.execute("SELECT closed_on FROM vacancies WHERE id = ?", (vacancy,)).fetchone()
        assert row["closed_on"] == "2026-10-27"
        assert conn.execute("SELECT 1 FROM starter_events WHERE offer_id = ?", (offer,)).fetchone()

    late = validate(
        client,
        workbook(
            (
                "Applications",
                {
                    "action": "add_application",
                    "application_id": "app-workbook-late",
                    "vacancy_id": vacancy,
                    "received_on": "2026-10-28",
                    "source_code": "careers",
                },
            )
        ),
    )
    assert late.status_code == 200, late.text
    assert late.json()["counts"]["invalid"] == 1
