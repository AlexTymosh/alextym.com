"""Isolated, persistent SQLite storage for the synthetic Fleet VOR Hub demo."""

from __future__ import annotations

import os
import json
import shutil
import sqlite3
import tempfile
from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

from fleet_hub.persistence import migrations as fleet_migrations
from fleet_hub.persistence.schema import bootstrap_lock
from fleet_hub.persistence.sqlite import open_sqlite

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
    # Hold the process lock through seed copying AND v1 migrations, but not
    # during subsequent business operations. ExitStack keeps the connection
    # open after the lock is released and closes it on every failure path.
    with ExitStack() as stack:
        with bootstrap_lock(path):
            created_from_seed = not path.exists()
            if created_from_seed:
                # Never expose a partially copied seed as the runtime database.
                with tempfile.NamedTemporaryFile(
                    prefix=f".{path.name}.seed-", suffix=".tmp", dir=path.parent, delete=False
                ) as staging:
                    staging_path = Path(staging.name)
                try:
                    shutil.copy2(SEED_FILE, staging_path)
                    os.replace(staging_path, path)
                finally:
                    staging_path.unlink(missing_ok=True)
            db = stack.enter_context(open_sqlite(path))
            if created_from_seed or not _legacy_store_schema_ready(db):
                _initialize_store_schema(db)
        yield db


def _legacy_store_schema_ready(db: sqlite3.Connection) -> bool:
    """Avoid repeated v1 DDL and migration calls on an initialized database.

    Missing tables, version markers or an incomplete booking initialization
    always use the existing idempotent bootstrap, including recovery behaviour.
    This check is read-only and uses persistent SQLite metadata, not a process
    cache; separate workers and restarts therefore see the same state.
    """
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('maintenance_bookings', 'vor_schema_versions')"
        )
    }
    if tables != {"maintenance_bookings", "vor_schema_versions"}:
        return False

    required = (
        "v1_ui_refresh_20261012",
        "v1_1_workflow_owners_20261012",
        "v1_2_subscribers_overdue_20261012",
    )
    completed = {
        row[0]
        for row in db.execute(
            "SELECT name FROM vor_schema_versions WHERE name IN (?, ?, ?)", required
        )
    }
    if len(completed) != len(required):
        return False

    # The previous bootstrap seeds bookings only when they are empty AND there
    # is no initialization marker. Keep this precise recovery contract.
    initialized = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vor_bookings_initialized'"
    ).fetchone()
    if initialized is not None:
        return True
    return db.execute("SELECT 1 FROM maintenance_bookings LIMIT 1").fetchone() is not None


def _initialize_store_schema(db: sqlite3.Connection) -> None:
    """Legacy Fleet schema bootstrap; will be further isolated after characterization."""
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


def migrate_v1_demo(db: sqlite3.Connection) -> None:
    """Backward-compatible entrypoint for the v1 UI refresh migration."""
    fleet_migrations.migrate_v1_demo(db)


def migrate_v1_1_demo(db: sqlite3.Connection) -> None:
    """Backward-compatible entrypoint for v1.1 workflow owners migration."""
    fleet_migrations.migrate_v1_1_demo(db, responsible_names=RESPONSIBLE_NAMES)


def migrate_v1_2_demo(db: sqlite3.Connection) -> None:
    """Backward-compatible entrypoint for v1.2 contacts/overdue migration."""
    fleet_migrations.migrate_v1_2_demo(db)


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
