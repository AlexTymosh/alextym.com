"""Isolated, persistent SQLite storage for the synthetic Fleet VOR Hub demo."""

from __future__ import annotations

import os
import json
import random
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

SEED_FILE = Path(__file__).with_name("vor_seed.sqlite3")
# Preserve backend/_local on Windows and /app/_local inside the existing Docker host.
# Relocating source must not reset an existing runtime SQLite database.
_REPO_ROOT = Path(__file__).resolve().parents[6]
_HOST_BACKEND = _REPO_ROOT / "backend"
_RUNTIME_ROOT = _HOST_BACKEND if (_HOST_BACKEND / "app").is_dir() else Path.cwd()
LOCAL_FILE = (_RUNTIME_ROOT / "_local" / "vor_hub.sqlite3").resolve()
EVENT_TYPES = {"internal", "email"}
BOOKING_TYPES = {"MOT", "Inspection", "Service"}
RESPONSIBLE_NAMES = ("Alex Tym", "Victoria B.", "Jason W.", "Janine M.", "Gosha T.")
SCENARIO_ISSUES = {
    "engine": "Engine failure / no start",
    "adblue": "AdBlue system fault",
    "door": "Door mechanism fault",
    "electrical": "Electrical fault",
    "tyre": "Tyre puncture / wear",
    "gearbox": "Gearbox fault",
    "fuel": "Fuel injection fault",
    "brakes": "Brake system fault",
    "mot": "MOT inspection",
    "service": "Scheduled service",
    "inspection": "Vehicle safety inspection",
    "glass": "Windscreen damage",
    "cooling": "Cooling system fault",
}


def database_path() -> Path:
    raw = os.getenv("VOR_DEMO_DB_PATH", "").strip()
    return Path(raw).expanduser().resolve() if raw else LOCAL_FILE


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        shutil.copy2(SEED_FILE, path)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=15000")
    db.executescript("""
      CREATE TABLE IF NOT EXISTS maintenance_bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        kind TEXT NOT NULL CHECK(kind IN ('MOT','Inspection','Service')),
        booked_date TEXT NOT NULL,
        garage TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Booked',
        created_at TEXT NOT NULL,
        UNIQUE(vehicle_id,kind,booked_date)
      );
    """)
    # Seed bookings only once per fresh demo database; keep user changes on subsequent launches.
    if (
        db.execute("SELECT COUNT(*) FROM maintenance_bookings").fetchone()[0] == 0
        and not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vor_bookings_initialized'"
        ).fetchone()
    ):
        db.execute("CREATE TABLE vor_bookings_initialized (singleton INTEGER PRIMARY KEY)")
        vehicles = db.execute(
            "SELECT id, mot_due, inspection_due, service_due, garage FROM vehicles ORDER BY id"
        ).fetchall()
        for v in vehicles:
            for kind, col, modulus in [
                ("MOT", "mot_due", 3),
                ("Inspection", "inspection_due", 4),
                ("Service", "service_due", 5),
            ]:
                if v["id"] % modulus != 0:
                    db.execute(
                        "INSERT INTO maintenance_bookings(vehicle_id,kind,booked_date,garage,status,created_at) VALUES(?,?,?,?,?,?)",
                        (v["id"], kind, v[col], v["garage"], "Booked", "2026-10-12T08:00:00"),
                    )
        db.execute("INSERT INTO vor_bookings_initialized VALUES (1)")
        db.commit()
    migrate_v1_demo(db)
    migrate_v1_1_demo(db)
    migrate_v1_2_demo(db)
    # Contact edits from Manage are authoritative; never overwrite them from old env values.
    try:
        yield db
    finally:
        db.close()


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


def migrate_v1_1_demo(db: sqlite3.Connection) -> None:
    """Assign five demo staff members as responsible owners once; retain custom user changes."""
    version = "v1_1_workflow_owners_20261012"
    if db.execute("SELECT 1 FROM vor_schema_versions WHERE name=?", (version,)).fetchone():
        return
    rng = random.Random(20261012)
    for vehicle in db.execute("SELECT id FROM vehicles ORDER BY id"):
        db.execute(
            "UPDATE vehicles SET responsible=? WHERE id=?",
            (rng.choice(RESPONSIBLE_NAMES), vehicle["id"]),
        )
    db.execute(
        "INSERT INTO vor_schema_versions(name,applied_at) VALUES (?,?)",
        (version, datetime.now().isoformat(timespec="seconds")),
    )
    db.commit()


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


def sync_private_demo_emails(db: sqlite3.Connection) -> None:
    """Legacy helper retained for compatibility, no longer called. Edit via Manage."""
    changed = False
    for key, name in [
        ("VOR_DEMO_ALEX_EMAIL", "Alex Tym"),
        ("VOR_DEMO_VICTORIA_EMAIL", "Victoria B."),
    ]:
        email = os.getenv(key, "").strip().lower()
        if not email:
            continue
        row = db.execute("SELECT id,email FROM contacts WHERE name=?", (name,)).fetchone()
        if row and row["email"] != email:
            db.execute("UPDATE contacts SET email=? WHERE id=?", (email, row["id"]))
            changed = True
    if changed:
        db.commit()


def subscriber_emails(vehicle_id: int) -> list[str]:
    """Authoritative per-vehicle notification list; never trust addresses sent by browser."""
    with connection() as db:
        rows = db.execute(
            """SELECT DISTINCT lower(trim(c.email)) AS email FROM subscriptions s
             JOIN contacts c ON c.id=s.contact_id
             WHERE s.vehicle_id=? AND s.is_subscriber=1 ORDER BY email""",
            (vehicle_id,),
        ).fetchall()
        return [str(r["email"]) for r in rows if r["email"]]


def change_responsible(vehicle_id: int, name: str) -> None:
    if name not in RESPONSIBLE_NAMES:
        raise ValueError("Unknown responsible person")
    with connection() as db:
        old = db.execute("SELECT responsible FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if old is None:
            raise ValueError("Vehicle not found")
        if old["responsible"] == name:
            return
        db.execute("UPDATE vehicles SET responsible=? WHERE id=?", (name, vehicle_id))
        db.execute(
            "INSERT INTO events(vehicle_id,kind,author,body,created_at,is_demo) VALUES (?,?,?,?,?,1)",
            (
                vehicle_id,
                "internal",
                "Fleet Hub",
                f"Responsible changed: {old['responsible']} → {name}",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()


def change_workshop(vehicle_id: int, garage: str) -> None:
    garage = garage.strip()
    if not garage:
        raise ValueError("Workshop is required")
    with connection() as db:
        old = db.execute("SELECT garage FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if old is None:
            raise ValueError("Vehicle not found")
        if old["garage"] == garage:
            return
        db.execute("UPDATE vehicles SET garage=? WHERE id=?", (garage, vehicle_id))
        db.execute(
            "INSERT INTO events(vehicle_id,kind,author,body,created_at,is_demo) VALUES (?,?,?,?,?,1)",
            (
                vehicle_id,
                "internal",
                "Fleet Hub",
                f"Workshop changed: {old['garage']} → {garage}",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()


def change_workflow_scenario(vehicle_id: int, ticket_id: str, scenario: str) -> None:
    """Switch the selected OPEN ticket to a different template and reset its stage progress.

    Does not change VOR availability status. An MOT workflow may be used for demo purposes
    even when the vehicle remains VOR. The original activity history is preserved.
    """
    with connection() as db:
        ticket = db.execute(
            "SELECT id,scenario,status FROM tickets WHERE id=? AND vehicle_id=?",
            (ticket_id, vehicle_id),
        ).fetchone()
        if not ticket:
            raise ValueError("Ticket does not belong to vehicle")
        if ticket["status"] != "open":
            raise ValueError("Only open tickets can change scenario")
        if db.execute(
            "SELECT 1 FROM vor_cases WHERE legacy_ticket_id=? AND pathway IN ('tyres','windscreen')",
            (ticket_id,),
        ).fetchone():
            raise ValueError("Specialist repairs are managed by the HOTH team")
        template = db.execute(
            "SELECT name,steps_json FROM workflow_templates WHERE code=?", (scenario,)
        ).fetchone()
        if not template:
            raise ValueError("Unknown workflow scenario")
        if ticket["scenario"] == scenario:
            return
        steps = json.loads(template["steps_json"])
        if not isinstance(steps, list) or not steps or not all(isinstance(x, str) for x in steps):
            raise ValueError("Workflow template is invalid")
        # Transactional reset affects this ticket's stages only.
        issue = SCENARIO_ISSUES.get(scenario, str(template["name"]))
        ticket_kind = {"mot": "MOT", "service": "SERVICE", "inspection": "INSPECTION"}.get(
            scenario, "DEFECT"
        )
        db.execute(
            "UPDATE tickets SET scenario=?,title=?,kind=? WHERE id=?",
            (scenario, issue, ticket_kind, ticket_id),
        )
        for table_name in ("vor_step_checklists", "ops_stage_skips", "ops_release_checks"):
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
            ).fetchone():
                db.execute(f"DELETE FROM {table_name} WHERE ticket_id=?", (ticket_id,))
        db.execute("DELETE FROM ticket_steps WHERE ticket_id=?", (ticket_id,))
        db.executemany(
            "INSERT INTO ticket_steps(ticket_id,step_index,label,status) VALUES (?,?,?,?)",
            [
                (ticket_id, i, label, "current" if i == 0 else "pending")
                for i, label in enumerate(steps)
            ],
        )
        # Update the selected vehicle's scenario and next action when this ticket is being edited.
        db.execute(
            "UPDATE vehicles SET scenario=?,issue=?,workflow_current_step=0,next_action=? WHERE id=?",
            (scenario, issue, steps[0], vehicle_id),
        )
        db.execute(
            "INSERT INTO events(vehicle_id,ticket_id,kind,author,body,created_at,is_demo) VALUES (?,?,?,?,?,?,1)",
            (
                vehicle_id,
                ticket_id,
                "internal",
                "Fleet Hub",
                f"Workflow changed: {ticket['scenario']} → {template['name']}; stages restarted",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()


def rows(db: sqlite3.Connection, query: str, args: tuple = ()) -> list[dict[str, Any]]:
    return [dict(item) for item in db.execute(query, args).fetchall()]


def snapshot() -> dict[str, Any]:
    from fleet_hub.services import vor_data

    with vor_data.database() as db:
        return {
            "vehicles": rows(
                db,
                "SELECT * FROM vehicles WHERE COALESCE(is_archived,0)=0 ORDER BY (availability_status = 'VOR') DESC, vor_days DESC, id",
            ),
            "tickets": rows(db, "SELECT * FROM tickets ORDER BY opened_at DESC"),
            "events": rows(db, "SELECT * FROM events ORDER BY created_at, id"),
            "steps": rows(db, "SELECT * FROM ticket_steps ORDER BY ticket_id, step_index"),
            "workflows": rows(db, "SELECT * FROM workflow_templates ORDER BY name"),
            "contacts": rows(db, "SELECT * FROM contacts ORDER BY name"),
            "subscriptions": rows(db, "SELECT * FROM subscriptions WHERE is_subscriber=1"),
            "bookings": rows(db, "SELECT * FROM maintenance_bookings ORDER BY booked_date, id"),
            "daily": rows(db, "SELECT * FROM dashboard_daily_stats ORDER BY date"),
            "today": date.today().isoformat(),
        }


def validate_vehicle_ticket(vehicle_id: int, ticket_id: str | None) -> str:
    """Resolve registration and validate ticket BEFORE any external delivery."""
    with connection() as db:
        vehicle = db.execute(
            "SELECT registration FROM vehicles WHERE id=?", (vehicle_id,)
        ).fetchone()
        if not vehicle:
            raise ValueError("Vehicle not found")
        if (
            ticket_id
            and not db.execute(
                "SELECT 1 FROM tickets WHERE id=? AND vehicle_id=?", (ticket_id, vehicle_id)
            ).fetchone()
        ):
            raise ValueError("Ticket does not belong to vehicle")
        return str(vehicle["registration"])


def add_event(
    vehicle_id: int,
    ticket_id: str | None,
    kind: str,
    text: str,
    author: str,
    *,
    subject: str | None = None,
    recipient: str | None = None,
    direction: str | None = None,
) -> int:
    if kind not in EVENT_TYPES and kind != "maintenance":
        raise ValueError("Unsupported event type")
    with connection() as db:
        if not db.execute("SELECT id FROM vehicles WHERE id=?", (vehicle_id,)).fetchone():
            raise ValueError("Vehicle not found")
        if (
            ticket_id
            and not db.execute(
                "SELECT id FROM tickets WHERE vehicle_id=? AND id=?", (vehicle_id, ticket_id)
            ).fetchone()
        ):
            raise ValueError("Ticket does not belong to vehicle")
        now = datetime.now().isoformat(timespec="seconds")
        result = db.execute(
            """INSERT INTO events(vehicle_id,ticket_id,kind,author,body,created_at,subject,recipient_email,direction,is_demo)
                             VALUES (?,?,?,?,?,?,?,?,?,1)""",
            (vehicle_id, ticket_id, kind, author, text, now, subject, recipient, direction),
        )
        db.commit()
        return int(result.lastrowid)


def email_count_today() -> int:
    with connection() as db:
        recipients = db.execute(
            "SELECT recipient_email FROM events WHERE kind='email' AND direction='outgoing' AND substr(created_at,1,10)=?",
            (date.today().isoformat(),),
        ).fetchall()
        return sum(
            len([v for v in (row["recipient_email"] or "").split(",") if v.strip()])
            for row in recipients
        )


def add_booking(vehicle_id: int, kind: str, booked_date: str, garage: str) -> int:
    if kind not in BOOKING_TYPES:
        raise ValueError("Invalid booking type")
    when = date.fromisoformat(booked_date)
    if when < date.today():
        raise ValueError("Booking must be today or later")
    if not 1 <= len(garage.strip()) <= 100:
        raise ValueError("Garage is required")
    with connection() as db:
        if not db.execute("SELECT id FROM vehicles WHERE id=?", (vehicle_id,)).fetchone():
            raise ValueError("Vehicle not found")
        cursor = db.execute(
            """INSERT INTO maintenance_bookings(vehicle_id,kind,booked_date,garage,status,created_at)
                               VALUES (?,?,?,?,?,?)""",
            (
                vehicle_id,
                kind,
                booked_date,
                garage.strip(),
                "Booked",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.execute(
            """INSERT INTO events(vehicle_id,kind,author,body,created_at,is_demo)
                      VALUES (?,?,?,?,?,1)""",
            (
                vehicle_id,
                "maintenance",
                "Fleet planner",
                f"{kind} booked at {garage.strip()} for {booked_date}",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()
        return int(cursor.lastrowid)


def advance_workflow(vehicle_id: int, ticket_id: str) -> None:
    """Advance the chosen ticket based on its own persisted current step."""
    with connection() as db:
        if not db.execute("SELECT id FROM vehicles WHERE id=?", (vehicle_id,)).fetchone():
            raise ValueError("Vehicle not found")
        ticket = db.execute(
            "SELECT status FROM tickets WHERE id=? AND vehicle_id=?", (ticket_id, vehicle_id)
        ).fetchone()
        if ticket is None:
            raise ValueError("Ticket does not belong to vehicle")
        if ticket["status"] != "open":
            raise ValueError("Ticket is not open")
        step = db.execute(
            "SELECT step_index,label FROM ticket_steps WHERE ticket_id=? AND status='current' ORDER BY step_index LIMIT 1",
            (ticket_id,),
        ).fetchone()
        if step is None:
            raise ValueError("Workflow complete or not available for this ticket")
        cur = int(step["step_index"])
        db.execute(
            "UPDATE ticket_steps SET status='done' WHERE ticket_id=? AND step_index=?",
            (ticket_id, cur),
        )
        next_step = db.execute(
            "SELECT step_index,label FROM ticket_steps WHERE ticket_id=? AND step_index>? ORDER BY step_index LIMIT 1",
            (ticket_id, cur),
        ).fetchone()
        if next_step:
            db.execute(
                "UPDATE ticket_steps SET status='current' WHERE ticket_id=? AND step_index=?",
                (ticket_id, next_step["step_index"]),
            )
        db.execute(
            "UPDATE vehicles SET workflow_current_step=?,next_action=? WHERE id=?",
            (
                int(next_step["step_index"]) if next_step else cur + 1,
                str(next_step["label"]) if next_step else "All workflow stages completed",
                vehicle_id,
            ),
        )
        db.execute(
            "INSERT INTO events(vehicle_id,ticket_id,kind,author,body,created_at,is_demo) VALUES (?,?,?,?,?,?,1)",
            (
                vehicle_id,
                ticket_id,
                "internal",
                "Fleet Hub",
                f"Workflow step completed: {step['label']}",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()


def add_contact(name: str, email: str, role: str) -> int:
    if role not in {"internal", "external"}:
        raise ValueError("Invalid role")
    with connection() as db:
        existing = db.execute(
            "SELECT id FROM contacts WHERE lower(email)=lower(?)", (email,)
        ).fetchone()
        if existing:
            return int(existing["id"])
        cur = db.execute(
            "INSERT INTO contacts(name,email,role) VALUES(?,?,?)",
            (name.strip(), email.strip(), role),
        )
        db.commit()
        return int(cur.lastrowid)


def toggle_subscriber(vehicle_id: int, contact_id: int, subscribed: bool) -> None:
    with connection() as db:
        if (
            not db.execute("SELECT 1 FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
            or not db.execute("SELECT 1 FROM contacts WHERE id=?", (contact_id,)).fetchone()
        ):
            raise ValueError("Vehicle or contact not found")
        db.execute(
            """INSERT INTO subscriptions(vehicle_id,contact_id,is_subscriber) VALUES(?,?,?)
                      ON CONFLICT(vehicle_id,contact_id) DO UPDATE SET is_subscriber=excluded.is_subscriber""",
            (vehicle_id, contact_id, 1 if subscribed else 0),
        )
        db.commit()


def update_contact(contact_id: int, name: str, email: str, role: str) -> None:
    # Manage is authoritative for address-book changes.
    if role not in {"internal", "external"}:
        raise ValueError("Invalid role")
    name = name.strip()
    email = email.strip().lower()
    if not name or not email:
        raise ValueError("Name and email are required")
    with connection() as db:
        if db.execute("SELECT 1 FROM contacts WHERE id=?", (contact_id,)).fetchone() is None:
            raise ValueError("Contact not found")
        duplicate = db.execute(
            "SELECT id FROM contacts WHERE lower(email)=? AND id<>?", (email, contact_id)
        ).fetchone()
        if duplicate:
            raise ValueError("This email belongs to another contact")
        db.execute(
            "UPDATE contacts SET name=?, email=?, role=? WHERE id=?",
            (name, email, role, contact_id),
        )
        db.commit()


def reserve_email_delivery(recipient_count: int, daily_limit: int) -> int:
    # Atomic daily quota. Failed/uncertain deliveries also consume quota.
    if recipient_count <= 0 or daily_limit <= 0:
        raise ValueError("Invalid email reservation")
    with connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS vor_email_delivery_attempts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          day TEXT NOT NULL,
          recipient_count INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending'
        )""")
        db.execute("BEGIN IMMEDIATE")
        count = db.execute(
            "SELECT COALESCE(SUM(recipient_count),0) FROM vor_email_delivery_attempts WHERE day=?",
            (date.today().isoformat(),),
        ).fetchone()[0]
        if count + recipient_count > daily_limit:
            raise ValueError("Daily recipient limit would be exceeded")
        cur = db.execute(
            "INSERT INTO vor_email_delivery_attempts(day,recipient_count,created_at) VALUES(?,?,?)",
            (
                date.today().isoformat(),
                recipient_count,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()
        return int(cur.lastrowid)


def finish_email_delivery(reservation_id: int, result: str) -> None:
    with connection() as db:
        db.execute(
            "UPDATE vor_email_delivery_attempts SET status=? WHERE id=?", (result, reservation_id)
        )
        db.commit()
