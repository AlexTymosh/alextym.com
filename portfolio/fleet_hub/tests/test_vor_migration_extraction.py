"""Compatibility and behaviour contracts for the extracted Fleet v1 migrations.

All SQLite files are disposable pytest tmp_path databases; never use runtime DB.
"""

from __future__ import annotations

from fleet_hub.persistence import migrations
from fleet_hub.services import vor_store


def test_store_migration_facades_keep_legacy_call_contract(monkeypatch) -> None:
    marker = object()
    calls: list[tuple[object, ...]] = []
    assigned = ("Owner A", "Owner B")
    monkeypatch.setattr(vor_store, "RESPONSIBLE_NAMES", assigned)
    monkeypatch.setattr(
        migrations,
        "migrate_v1_demo",
        lambda db: calls.append(("v1", db)),
    )
    monkeypatch.setattr(
        migrations,
        "migrate_v1_1_demo",
        lambda db, responsible_names: calls.append(("v1.1", db, responsible_names)),
    )
    monkeypatch.setattr(
        migrations,
        "migrate_v1_2_demo",
        lambda db: calls.append(("v1.2", db)),
    )

    vor_store.migrate_v1_demo(marker)
    vor_store.migrate_v1_1_demo(marker)
    vor_store.migrate_v1_2_demo(marker)

    assert calls == [
        ("v1", marker),
        ("v1.1", marker, assigned),
        ("v1.2", marker),
    ]


def test_migration_versions_are_idempotent_and_keep_manual_changes(monkeypatch, tmp_path) -> None:
    active = tmp_path / "migration-preservation.sqlite3"
    monkeypatch.setenv("VOR_DEMO_DB_PATH", str(active))

    with vor_store.connection() as db:
        versions_before = {
            row[0] for row in db.execute("SELECT name FROM vor_schema_versions").fetchall()
        }
        assert {
            "v1_ui_refresh_20261012",
            "v1_1_workflow_owners_20261012",
            "v1_2_subscribers_overdue_20261012",
        }.issubset(versions_before)
        db.execute("UPDATE vehicles SET responsible=? WHERE id=1", ("Owner Assigned",))
        db.commit()

    with vor_store.connection() as db:
        versions_after = {
            row[0] for row in db.execute("SELECT name FROM vor_schema_versions").fetchall()
        }
        responsible = db.execute("SELECT responsible FROM vehicles WHERE id=1").fetchone()[0]
        assert versions_after == versions_before
        assert responsible == "Owner Assigned"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
