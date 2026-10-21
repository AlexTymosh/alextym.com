"""PR-02: v2 migration/import/case/status behaviours; never touches the frozen v1 DB."""
import base64
import csv
import io
import sqlite3
import zipfile
from contextlib import contextmanager

import pytest

from app.services import vor_data, vor_store, vor_store_v1


@pytest.fixture
def databases(monkeypatch, tmp_path):
    active = tmp_path / "v2.sqlite3"
    frozen = tmp_path / "v1.sqlite3"
    # Self-contained representative legacy schema: exercise additive migrations.
    create = """
        PRAGMA foreign_keys=ON;
        CREATE TABLE vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL, availability_status TEXT NOT NULL,
            severity TEXT NOT NULL, issue TEXT NOT NULL,
            scenario TEXT NOT NULL, garage TEXT NOT NULL,
            vor_days INTEGER NOT NULL, workflow_current_step INTEGER NOT NULL,
            next_action TEXT NOT NULL, responsible TEXT NOT NULL,
            action_due TEXT NOT NULL, mot_due TEXT NOT NULL,
            inspection_due TEXT NOT NULL, service_due TEXT NOT NULL,
            odometer_miles INTEGER NOT NULL, unread_count INTEGER NOT NULL
        );
        CREATE TABLE tickets (
            id TEXT PRIMARY KEY, vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            title TEXT NOT NULL, scenario TEXT NOT NULL, status TEXT NOT NULL,
            hoth_reference TEXT, opened_at TEXT NOT NULL
        );
        INSERT INTO vehicles(registration,model,availability_status,severity,issue,scenario,
            garage,vor_days,workflow_current_step,next_action,responsible,action_due,mot_due,
            inspection_due,service_due,odometer_miles,unread_count)
        VALUES ('GX24 KLM','Ford Transit 350','VOR','Critical','No start','engine',
                'Nursling',6,2,'Await quote','Alex Tym','2026-11-04','2026-11-04',
                '2026-11-04','2026-11-04',20000,2);
        INSERT INTO tickets(id,vehicle_id,title,scenario,status,hoth_reference,opened_at)
            VALUES('PS001',1,'Engine issue','engine','open','HOTH-X','2026-10-18T10:00:00');
    """
    for path in (active, frozen):
        with sqlite3.connect(path) as db:
            db.executescript(create)
            db.commit()

    @contextmanager
    def connection():
        db = sqlite3.connect(active, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(vor_store, "database_path", lambda: active)
    monkeypatch.setattr(vor_store, "connection", connection)
    monkeypatch.setattr(vor_store_v1, "database_path", lambda: frozen)
    return active, frozen


def encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def csv_data(rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows([["Registration", "Model", "Garage"], *rows])
    return buf.getvalue().encode()


def xlsx_data():
    # Minimal Excel-compliant XLSX with inline strings. Exercise ZIP/XML parser.
    rows = [
        ["Registration", "Model", "Garage"],
        ["QP26 XYZ", "Mercedes Sprinter", "Reading"],
    ]
    worksheet = ['<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for idx, row in enumerate(rows, 1):
        worksheet.append(f'<row r="{idx}">')
        for col, val in zip("ABC", row):
            worksheet.append(f'<c r="{col}{idx}" t="inlineStr"><is><t>{val}</t></is></c>')
        worksheet.append("</row>")
    worksheet.append("</sheetData></worksheet>")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Fleet" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", "".join(worksheet))
    return output.getvalue()


def test_backfill_idempotent_and_v1_untouched(databases):
    active, frozen = databases
    frozen_before = frozen.read_bytes()
    state = vor_data.register_list()
    assert len(state["vehicles"]) == 1
    assert len(state["cases"]) == 1
    assert state["cases"][0]["legacy_ticket_id"] == "PS001"
    assert state["cases"][0]["hoth_reference"] == "HOTH-X"
    assert len(state["statuses"]) == 1
    assert state["statuses"][0]["event_kind"] == "baseline"
    state_again = vor_data.register_list()
    assert state_again["cases"] == state["cases"]
    assert state_again["statuses"] == state["statuses"]
    assert frozen.read_bytes() == frozen_before
    with sqlite3.connect(active) as db:
        assert db.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 1


def test_csv_preview_commit_repeat_update_and_preserve_status(databases):
    data = csv_data([["gx24klm", "Ford new model", "Oxford"], ["AB22 CDE", "Iveco Daily", "Didcot"]])
    payload = encode(data)
    p = vor_data.prepare_import("fleet.csv", payload, "skip")
    assert p["summary"] == {"insert": 1, "update": 0, "skip": 1}
    result = vor_data.commit_import("fleet.csv", payload, "skip", p["digest"])
    assert result["summary"] == {"insert": 1, "update": 0, "skip": 1}
    assert vor_data.commit_import("fleet.csv", payload, "skip", p["digest"])["repeated"] is True
    state = vor_data.register_list()
    assert len(state["vehicles"]) == 2
    original = next(v for v in state["vehicles"] if v["registration"] == "GX24 KLM")
    assert original["model"] == "Ford Transit 350" and original["availability_status"] == "VOR"
    assert vor_data.commit_import("fleet.csv", payload, "update", p["digest"])["summary"]["update"] == 1
    updated = next(v for v in vor_data.register_list()["vehicles"] if v["registration"] == "GX24 KLM")
    assert updated["model"] == "Ford new model" and updated["availability_status"] == "VOR"
    assert len(vor_data.register_list()["cases"]) == 1


def test_xlsx_and_manual_register_and_archive(databases):
    binary = xlsx_data()
    preview = vor_data.prepare_import("fleet.xlsx", encode(binary), "skip")
    assert not preview["errors"]
    assert preview["summary"]["insert"] == 1
    vor_data.commit_import("fleet.xlsx", encode(binary), "skip", preview["digest"])
    added = vor_data.register_vehicle("CC20 ZZZ", "Ford", "Basingstoke")
    assert added["registration"] == "CC20 ZZZ"
    with pytest.raises(ValueError, match="already"):
        vor_data.register_vehicle("cc20zzz", "Other", "Basingstoke")
    assert vor_data.archive_vehicle(added["id"], True)["changed"] is True
    assert not any(v["id"] == added["id"] for v in vor_data.register_list()["vehicles"])
    assert any(v["id"] == added["id"] for v in vor_data.register_list(True)["vehicles"])
    assert vor_data.archive_vehicle(added["id"], False)["changed"] is True


def test_status_only_changes_by_explicit_manual_confirmation(databases):
    vor_data.register_list()
    with pytest.raises(ValueError,match="Fleet Department"):
        vor_data.update_status(1, "Operational", "System", "release", "KEY2-X")
    state = vor_data.register_list()
    assert len(state["statuses"]) == 1
    assert vor_data.update_status(1, "Operational", "Fleet Department", "Confirmed available", "KEY2-X")["changed"]
    assert not vor_data.update_status(1,"Operational","Fleet Department","Repeated","KEY2-X")["changed"]
    state = vor_data.register_list()
    assert len(state["statuses"]) == 2
    assert state["statuses"][0]["old_status"] == "VOR"
    assert state["statuses"][0]["new_status"] == "Operational"
    assert state["statuses"][0]["external_reference"] == "KEY2-X"


def test_validation_rejects_duplicates_bad_digest_formula(databases):
    duplicate=csv_data([["AA20 BBB","Model","Garage"],["aa20bbb","Model","Garage"]])
    p=vor_data.prepare_import("x.csv",encode(duplicate),"skip")
    assert p["errors"]
    with pytest.raises(ValueError,match="validation errors"):
        vor_data.commit_import("x.csv",encode(duplicate),"skip",p["digest"])
    good=csv_data([["AA20 BBB","Model","Garage"]])
    preview=vor_data.prepare_import("x.csv",encode(good),"skip")
    with pytest.raises(ValueError,match="changed"):
        vor_data.commit_import("x.csv",encode(good),"skip","0"*64)
    with pytest.raises(ValueError,match="Only .csv and .xlsx"):
        vor_data.prepare_import("data.xls",encode(good),"skip")
    with pytest.raises(ValueError,match="registration"):
        vor_data.prepare_import("x.csv",encode(b"wrong,model,garage\na,ford,oxford"),"skip")


def test_fail_closed_if_paths_share_one_file(databases,monkeypatch):
    from app.services import vor_store_v1
    active,_ = databases
    monkeypatch.setattr(vor_store_v1,"database_path",lambda: active)
    with pytest.raises(RuntimeError,match="different"):
        vor_data.register_list()


def test_xlsx_formula_cells_are_rejected(databases):
    workbook = xlsx_data()
    input_buffer = io.BytesIO(workbook)
    output = io.BytesIO()
    with zipfile.ZipFile(input_buffer, "r") as source, zipfile.ZipFile(output, "w") as target:
        for member in source.infolist():
            data = source.read(member.filename)
            if member.filename == "xl/worksheets/sheet1.xml":
                data = data.replace(b'<c r="B2" t="inlineStr"><is><t>Mercedes Sprinter</t></is></c>',
                    b'<c r="B2"><f>HYPERLINK("http://invalid")</f><v>1</v></c>')
            target.writestr(member, data)
    with pytest.raises(ValueError, match="Formula cells"):
        vor_data.prepare_import("fleet.xlsx", encode(output.getvalue()), "skip")


def test_xlsx_shared_strings(databases):
    workbook = xlsx_data()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(workbook)) as original, zipfile.ZipFile(out, "w") as target:
        for member in original.infolist():
            body=original.read(member.filename)
            if member.filename=="xl/worksheets/sheet1.xml":
                body=body.replace(b'<c r="A2" t="inlineStr"><is><t>QP26 XYZ</t></is></c>',b'<c r="A2" t="s"><v>0</v></c>')
            target.writestr(member,body)
        target.writestr("xl/sharedStrings.xml",'<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>QP26 XYZ</t></si></sst>')
    preview = vor_data.prepare_import("fleet.xlsx",encode(out.getvalue()),"skip")
    assert preview["preview"][0]["registration"]=="QP26 XYZ"


def test_active_case_prevents_accidental_archive(databases):
    vor_data.register_list()
    with pytest.raises(ValueError,match="Open defect case"):
        vor_data.archive_vehicle(1,True)
    state = vor_data.register_list()
    assert state["vehicles"][0]["is_archived"]==0
