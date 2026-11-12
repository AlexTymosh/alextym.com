"""One-time v1 Fleet SQLite migrations.

One-time per-version migration execution; no HTTP or request handlers.
Each existing successful commit boundary is preserved. Failures roll back
pending writes and restore the connection's original foreign-key setting.
"""

from __future__ import annotations

import os
import random
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Callable


def _rollback_failed_migration(migrate: Callable[..., None]) -> Callable[..., None]:
    """Leave the caller's connection usable when a migration is interrupted.

    Migration implementations own their existing successful commits. On error,
    undo uncommitted changes before resetting PRAGMA foreign_keys, because
    SQLite cannot switch that pragma inside an active transaction.
    """

    @wraps(migrate)
    def guarded(db: sqlite3.Connection, *args: object, **kwargs: object) -> None:
        foreign_keys_before = bool(db.execute("PRAGMA foreign_keys").fetchone()[0])
        try:
            migrate(db, *args, **kwargs)
        except BaseException:
            db.rollback()
            foreign_keys_after = bool(db.execute("PRAGMA foreign_keys").fetchone()[0])
            if foreign_keys_before != foreign_keys_after:
                setting = "ON" if foreign_keys_before else "OFF"
                db.execute(f"PRAGMA foreign_keys={setting}")
            raise

    return guarded


@_rollback_failed_migration
def migrate_v1_demo(db: sqlite3.Connection) -> None:
    """One-time v1 data refresh, also applies to users' existing _local SQLite file.

    Preserves user-created messages, appointments, contacts, and workflow progress.
    The demo's original default subscriber assignments are replaced once.
    """
    db.execute(
        "CREATE TABLE IF NOT EXISTS vor_schema_versions (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    if db.execute(
        "SELECT 1 FROM vor_schema_versions WHERE name='v1_ui_refresh_20261012'"
    ).fetchone():
        return

    # All ticket ids become PS000xxx; references are checked again after migration.
    db.commit()
    db.execute("PRAGMA foreign_keys=OFF")
    original = [r["id"] for r in db.execute("SELECT id FROM tickets ORDER BY id").fetchall()]
    for idx, old_id in enumerate(original, 100):
        new_id = f"PS000{idx:03d}"
        if old_id == new_id:
            continue
        db.execute("UPDATE tickets SET id=? WHERE id=?", (new_id, old_id))
        db.execute("UPDATE ticket_steps SET ticket_id=? WHERE ticket_id=?", (new_id, old_id))
        db.execute("UPDATE events SET ticket_id=? WHERE ticket_id=?", (new_id, old_id))
        # Earlier synthetic emails may mention the old reference in the body/subject.
        db.execute(
            "UPDATE events SET body=replace(body,?,?), subject=replace(subject,?,?)",
            (old_id, new_id, old_id, new_id),
        )

    db.execute("UPDATE vehicles SET model='Tesla Model Y' WHERE lower(model) LIKE 'iveco%'")
    # Names are invented demo identities (avoid using real business contacts).
    internal = [
        ("Alex Tym", "alex@fleet-demo.example"),
        ("Victoria B.", "victoria@fleet-demo.example"),
        ("Jason W.", "jason@fleet-demo.example"),
        ("Janine M.", "janine@fleet-demo.example"),
        ("Gosha T.", "gosha@fleet-demo.example"),
    ]
    external = [
        ("Steve EXHAUSTON", "steve@exhauston.example"),
        ("John CITYSIDE GARAGE", "john@cityside-garage.example"),
        ("Mark M&BRIDGE", "mark@mbridge-auto.example"),
    ]
    ids_internal = []
    ids_external = []
    for name, email in internal:
        row = db.execute("SELECT id FROM contacts WHERE lower(email)=lower(?)", (email,)).fetchone()
        if not row:
            row = db.execute("SELECT id FROM contacts WHERE name=?", (name,)).fetchone()
        if row:
            cid = int(row["id"])
            db.execute(
                "UPDATE contacts SET name=?,email=?,role=? WHERE id=?",
                (name, email, "internal", cid),
            )
        else:
            cid = int(
                db.execute(
                    "INSERT INTO contacts(name,email,role) VALUES(?,?,?)", (name, email, "internal")
                ).lastrowid
            )
        ids_internal.append(cid)
    for name, email in external:
        row = db.execute("SELECT id FROM contacts WHERE lower(email)=lower(?)", (email,)).fetchone()
        if row:
            cid = int(row["id"])
            db.execute("UPDATE contacts SET name=?,role=? WHERE id=?", (name, "external", cid))
        else:
            cid = int(
                db.execute(
                    "INSERT INTO contacts(name,email,role) VALUES(?,?,?)", (name, email, "external")
                ).lastrowid
            )
        ids_external.append(cid)
    # All visible subscriber chips follow the requested stable per-vehicle distribution.
    # Existing custom subscriptions beyond the seeded demo contacts remain available
    # in Manage, but the initial v1 refresh resets default memberships once.
    seeded_ids = [
        int(r["id"])
        for r in db.execute(
            "SELECT id FROM contacts WHERE email LIKE '%fleet-demo.example' OR email LIKE '%example.com'"
        )
    ]
    seeded_ids = set(seeded_ids) | set(ids_internal) | set(ids_external)
    for cid in seeded_ids:
        db.execute("DELETE FROM subscriptions WHERE contact_id=?", (cid,))
    rng = random.Random(20261012)
    for row in db.execute("SELECT id FROM vehicles ORDER BY id").fetchall():
        vid = int(row["id"])
        members = rng.sample(ids_internal, rng.choice([2, 3])) + [rng.choice(ids_external)]
        for cid in members:
            db.execute(
                "INSERT INTO subscriptions(vehicle_id,contact_id,is_subscriber) VALUES(?,?,1) ON CONFLICT(vehicle_id,contact_id) DO UPDATE SET is_subscriber=1",
                (vid, cid),
            )
    # Legacy sample supplier contacts are retained for draft-email address lookup
    # and do not appear as subscribers unless the user adds them manually.
    failed = db.execute("PRAGMA foreign_key_check").fetchall()
    if failed:
        db.rollback()
        raise RuntimeError(f"VOR demo schema migration foreign-key failure: {failed[:3]}")
    db.execute(
        "INSERT INTO vor_schema_versions(name,applied_at) VALUES(?,?)",
        ("v1_ui_refresh_20261012", datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
    db.execute("PRAGMA foreign_keys=ON")


@_rollback_failed_migration
def migrate_v1_1_demo(db: sqlite3.Connection, responsible_names: tuple[str, ...]) -> None:
    """Assign five demo staff members as responsible owners once; retain custom user changes."""
    version = "v1_1_workflow_owners_20261012"
    if db.execute("SELECT 1 FROM vor_schema_versions WHERE name=?", (version,)).fetchone():
        return
    rng = random.Random(20261012)
    for vehicle in db.execute("SELECT id FROM vehicles ORDER BY id"):
        db.execute(
            "UPDATE vehicles SET responsible=? WHERE id=?",
            (rng.choice(responsible_names), vehicle["id"]),
        )
    db.execute(
        "INSERT INTO vor_schema_versions(name,applied_at) VALUES (?,?)",
        (version, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()


@_rollback_failed_migration
def migrate_v1_2_demo(db: sqlite3.Connection) -> None:
    """One-time demo contacts and random overdue dates migration. Existing activity remains."""
    version = "v1_2_subscribers_overdue_20261012"
    if db.execute("SELECT 1 FROM vor_schema_versions WHERE name=?", (version,)).fetchone():
        return
    # Preserve manually added contacts. Remove only named original demo directory contacts.
    people = [
        (
            "Alex Tym",
            os.getenv("VOR_DEMO_ALEX_EMAIL", "alex@fleet-demo.example").strip().lower(),
            "internal",
        ),
        (
            "Victoria B.",
            os.getenv("VOR_DEMO_VICTORIA_EMAIL", "victoria@fleet-demo.example").strip().lower(),
            "internal",
        ),
        ("Steve EXHAUSTON", "steve@exhauston.example", "external"),
        ("John CITYSIDE GARAGE", "john@cityside-garage.example", "external"),
    ]
    people_ids = []
    for name, email, role in people:
        found = db.execute("SELECT id FROM contacts WHERE name=?", (name,)).fetchone()
        if found is None:
            found = db.execute(
                "SELECT id FROM contacts WHERE lower(email)=lower(?)", (email,)
            ).fetchone()
        if found is None:
            cid = int(
                db.execute(
                    "INSERT INTO contacts(name,email,role) VALUES(?,?,?)", (name, email, role)
                ).lastrowid
            )
        else:
            cid = int(found["id"])
            db.execute(
                "UPDATE contacts SET name=?,email=?,role=? WHERE id=?", (name, email, role, cid)
            )
        people_ids.append(cid)
    # Remove the superseded seed-only directory records, including default garages and 3 staff.
    obsolete = db.execute("SELECT id,name,email FROM contacts").fetchall()
    for r in obsolete:
        if int(r["id"]) in people_ids:
            continue
        old_demo = (
            r["email"].endswith("@fleet-demo.example")
            or r["email"].endswith("@example.com")
            or r["email"] in {"mark@mbridge-auto.example"}
        )
        if old_demo:
            db.execute("DELETE FROM subscriptions WHERE contact_id=?", (r["id"],))
            db.execute("DELETE FROM contacts WHERE id=?", (r["id"],))
    # All 20 vehicles subscribe to the two explicitly chosen addresses and one demo partner.
    # Demo partner must be removed or replaced before enabling REAL email delivery.
    rng = random.Random(20261012)
    for v in db.execute("SELECT id FROM vehicles ORDER BY id").fetchall():
        vid = int(v["id"])
        db.execute(
            "DELETE FROM subscriptions WHERE vehicle_id=? AND contact_id IN ("
            + ",".join("?" * len(people_ids))
            + ")",
            (vid, *people_ids),
        )
        for cid in (people_ids[0], people_ids[1], rng.choice(people_ids[2:])):
            db.execute(
                "INSERT INTO subscriptions(vehicle_id,contact_id,is_subscriber) VALUES(?,?,1)",
                (vid, cid),
            )
    # Stable overdue examples across different vehicle/kind combinations, including the first car.
    vehicles = [r["id"] for r in db.execute("SELECT id FROM vehicles ORDER BY id").fetchall()]
    kinds = ["mot_due", "inspection_due", "service_due"]
    rng2 = random.Random(20261013)
    selected = [(vehicles[0], "inspection_due")]
    pool = [(vid, col) for vid in vehicles for col in kinds if (vid, col) not in selected]
    selected += rng2.sample(pool, 11)
    for i, (vid, col) in enumerate(selected):
        overdue = (date.today() - timedelta(days=2 + ((i * 7 + 3) % 34))).isoformat()
        db.execute(f"UPDATE vehicles SET {col}=? WHERE id=?", (overdue, vid))
    db.execute(
        "INSERT INTO vor_schema_versions(name,applied_at) VALUES (?,?)",
        (version, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()
