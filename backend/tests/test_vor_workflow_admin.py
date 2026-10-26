"""PR14: custom workflow creation, stage dependency gates and v1 isolation."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest
from app.services import vor_store, vor_store_v1
from app.services import vor_workflow_admin as library


@pytest.fixture
def fixture_db(tmp_path, monkeypatch):
    active = tmp_path / "v2.sqlite3"
    frozen = tmp_path / "v1.sqlite3"
    frozen.write_bytes(b"frozen-v1-marker")
    with sqlite3.connect(active) as db:
        db.executescript("""
          PRAGMA foreign_keys=ON;
          CREATE TABLE vehicles(id INTEGER PRIMARY KEY, scenario TEXT);
          CREATE TABLE workflow_templates(code TEXT PRIMARY KEY,name TEXT NOT NULL,steps_json TEXT NOT NULL);
          CREATE TABLE tickets(id TEXT PRIMARY KEY,vehicle_id INTEGER,scenario TEXT NOT NULL REFERENCES workflow_templates(code),status TEXT);
          CREATE TABLE ticket_steps(ticket_id TEXT,step_index INTEGER,label TEXT,status TEXT,PRIMARY KEY(ticket_id,step_index));
          INSERT INTO workflow_templates VALUES('engine','Engine repair','["Fault reported","Repair done"]');
          INSERT INTO vehicles VALUES(1,'engine');
          INSERT INTO tickets VALUES('PS1',1,'engine','closed');
          INSERT INTO ticket_steps VALUES('PS1',0,'Fault reported','done');
          INSERT INTO ticket_steps VALUES('PS1',1,'Repair done','done');
        """)

    @contextmanager
    def connection():
        db = sqlite3.connect(active)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    # Service uses vor_data.database; patch directly to keep these tests independent
    # of the broad v2 migrations and embedded seeded demo database.
    from app.services import vor_workflow_admin

    monkeypatch.setattr(vor_workflow_admin.vor_data, "database", connection)
    monkeypatch.setattr(vor_store, "database_path", lambda: active)
    monkeypatch.setattr(vor_store_v1, "database_path", lambda: frozen)
    return active, frozen


def test_create_add_rename_delete_and_v1_unchanged(fixture_db):
    _, frozen = fixture_db
    before = frozen.read_bytes()
    result = library.create("Warranty repair", "New warranty case")
    code = result["code"]
    assert code.startswith("custom_")
    assert library.add_stage(code, "Warranty decision")["index"] == 1
    library.change_stage(code, 1, "Claim authorised")
    assert library.catalogue()["workflows"][-1]["steps"] == [
        "New warranty case",
        "Claim authorised",
    ]
    library.remove_stage(code, 1)
    assert len(next(w for w in library.catalogue()["workflows"] if w["code"] == code)["steps"]) == 1
    library.rename(code, "Custom warranty")
    library.remove_workflow(code)
    assert not any(w["code"] == code for w in library.catalogue()["workflows"])
    assert frozen.read_bytes() == before


def test_reference_blocks_delete_and_edit_even_on_closed_ticket(fixture_db):
    _, frozen = fixture_db
    with pytest.raises(ValueError, match="referenced by"):
        library.remove_workflow("engine")
    with pytest.raises(ValueError, match="depend on this position"):
        library.remove_stage("engine", 0)
    with pytest.raises(ValueError, match="already used"):
        library.change_stage("engine", 1, "Replace history")
    # Additions are prospective: historic ticket stage list remains unchanged.
    library.add_stage("engine", "Extra quality check")
    with sqlite3.connect(fixture_db[0]) as db:
        assert (
            db.execute("SELECT count(*) FROM ticket_steps WHERE ticket_id='PS1'").fetchone()[0] == 2
        )
    assert frozen.read_bytes() == b"frozen-v1-marker"


def test_invalid_and_assigned_workflow_guards(fixture_db):
    one = library.create("Single stage", "Only step")
    with pytest.raises(ValueError, match="at least one stage"):
        library.remove_stage(one["code"], 0)
    with pytest.raises(ValueError, match="already exists"):
        library.create("Engine repair", "New start")
    w = library.create("Review case", "Initial check")
    with sqlite3.connect(fixture_db[0]) as db:
        db.execute("INSERT INTO vehicles VALUES(2,?)", (w["code"],))
        db.commit()
    with pytest.raises(ValueError, match="assigned"):
        library.remove_workflow(w["code"])
