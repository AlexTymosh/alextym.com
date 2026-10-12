"""Isolated, persistent SQLite storage for the synthetic Fleet VOR Hub demo."""
from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

SEED_FILE = Path(__file__).with_name('vor_seed.sqlite3')
LOCAL_FILE = Path(__file__).resolve().parents[2] / '_local' / 'vor_hub.sqlite3'
EVENT_TYPES = {'internal', 'email'}
BOOKING_TYPES = {'MOT', 'Inspection', 'Service'}


def database_path() -> Path:
    raw = os.getenv('VOR_DEMO_DB_PATH', '').strip()
    return Path(raw).expanduser().resolve() if raw else LOCAL_FILE


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        shutil.copy2(SEED_FILE, path)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=15000')
    db.executescript('''
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
    ''')
    # Seed bookings only once per fresh demo database; keep user changes on subsequent launches.
    if db.execute("SELECT COUNT(*) FROM maintenance_bookings").fetchone()[0] == 0 and not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='vor_bookings_initialized'").fetchone():
        db.execute('CREATE TABLE vor_bookings_initialized (singleton INTEGER PRIMARY KEY)')
        vehicles = db.execute('SELECT id, mot_due, inspection_due, service_due, garage FROM vehicles ORDER BY id').fetchall()
        for v in vehicles:
            for kind, col, modulus in [('MOT','mot_due',3),('Inspection','inspection_due',4),('Service','service_due',5)]:
                if v['id'] % modulus != 0:
                    db.execute('INSERT INTO maintenance_bookings(vehicle_id,kind,booked_date,garage,status,created_at) VALUES(?,?,?,?,?,?)',
                               (v['id'],kind,v[col],v['garage'],'Booked','2026-10-12T08:00:00'))
        db.execute('INSERT INTO vor_bookings_initialized VALUES (1)')
        db.commit()
    try:
        yield db
    finally:
        db.close()


def rows(db: sqlite3.Connection, query: str, args: tuple = ()) -> list[dict[str, Any]]:
    return [dict(item) for item in db.execute(query, args).fetchall()]


def snapshot() -> dict[str, Any]:
    with connection() as db:
        return {
            'vehicles': rows(db, 'SELECT * FROM vehicles ORDER BY (availability_status = \'VOR\') DESC, vor_days DESC, id'),
            'tickets': rows(db, 'SELECT * FROM tickets ORDER BY opened_at DESC'),
            'events': rows(db, 'SELECT * FROM events ORDER BY created_at, id'),
            'steps': rows(db, 'SELECT * FROM ticket_steps ORDER BY ticket_id, step_index'),
            'workflows': rows(db, 'SELECT * FROM workflow_templates ORDER BY name'),
            'contacts': rows(db, 'SELECT * FROM contacts ORDER BY name'),
            'subscriptions': rows(db, 'SELECT * FROM subscriptions WHERE is_subscriber=1'),
            'bookings': rows(db, 'SELECT * FROM maintenance_bookings ORDER BY booked_date, id'),
            'daily': rows(db, 'SELECT * FROM dashboard_daily_stats ORDER BY date'),
            'today': date.today().isoformat(),
        }


def validate_vehicle_ticket(vehicle_id: int, ticket_id: str | None) -> str:
    """Resolve registration and validate ticket BEFORE any external delivery."""
    with connection() as db:
        vehicle = db.execute('SELECT registration FROM vehicles WHERE id=?', (vehicle_id,)).fetchone()
        if not vehicle:
            raise ValueError('Vehicle not found')
        if ticket_id and not db.execute('SELECT 1 FROM tickets WHERE id=? AND vehicle_id=?',(ticket_id,vehicle_id)).fetchone():
            raise ValueError('Ticket does not belong to vehicle')
        return str(vehicle['registration'])


def add_event(vehicle_id: int, ticket_id: str | None, kind: str, text: str, author: str,
              *, subject: str | None = None, recipient: str | None = None,
              direction: str | None = None) -> int:
    if kind not in EVENT_TYPES and kind != 'maintenance':
        raise ValueError('Unsupported event type')
    with connection() as db:
        if not db.execute('SELECT id FROM vehicles WHERE id=?', (vehicle_id,)).fetchone():
            raise ValueError('Vehicle not found')
        if ticket_id and not db.execute('SELECT id FROM tickets WHERE vehicle_id=? AND id=?', (vehicle_id,ticket_id)).fetchone():
            raise ValueError('Ticket does not belong to vehicle')
        now = datetime.now().isoformat(timespec='seconds')
        result = db.execute('''INSERT INTO events(vehicle_id,ticket_id,kind,author,body,created_at,subject,recipient_email,direction,is_demo)
                             VALUES (?,?,?,?,?,?,?,?,?,1)''',
                            (vehicle_id,ticket_id,kind,author,text,now,subject,recipient,direction))
        db.commit()
        return int(result.lastrowid)


def email_count_today() -> int:
    with connection() as db:
        return int(db.execute("SELECT count(*) FROM events WHERE kind='email' AND direction='outgoing' AND substr(created_at,1,10)=?", (date.today().isoformat(),)).fetchone()[0])


def add_booking(vehicle_id: int, kind: str, booked_date: str, garage: str) -> int:
    if kind not in BOOKING_TYPES:
        raise ValueError('Invalid booking type')
    when = date.fromisoformat(booked_date)
    if when < date.today():
        raise ValueError('Booking must be today or later')
    if not 1 <= len(garage.strip()) <= 100:
        raise ValueError('Garage is required')
    with connection() as db:
        if not db.execute('SELECT id FROM vehicles WHERE id=?', (vehicle_id,)).fetchone():
            raise ValueError('Vehicle not found')
        cursor = db.execute('''INSERT INTO maintenance_bookings(vehicle_id,kind,booked_date,garage,status,created_at)
                               VALUES (?,?,?,?,?,?)''',
                            (vehicle_id,kind,booked_date,garage.strip(),'Booked',datetime.now().isoformat(timespec='seconds')))
        db.execute('''INSERT INTO events(vehicle_id,kind,author,body,created_at,is_demo)
                      VALUES (?,?,?,?,?,1)''',
                   (vehicle_id,'maintenance','Fleet planner',f'{kind} booked at {garage.strip()} for {booked_date}',datetime.now().isoformat(timespec='seconds')))
        db.commit()
        return int(cursor.lastrowid)


def advance_workflow(vehicle_id: int, ticket_id: str) -> None:
    with connection() as db:
        v = db.execute('SELECT workflow_current_step FROM vehicles WHERE id=?', (vehicle_id,)).fetchone()
        ticket = db.execute('SELECT id FROM tickets WHERE id=? AND vehicle_id=?', (ticket_id,vehicle_id)).fetchone()
        if not v or not ticket:
            raise ValueError('Vehicle or ticket not found')
        cur = int(v['workflow_current_step'])
        step = db.execute('SELECT label FROM ticket_steps WHERE ticket_id=? AND step_index=?',(ticket_id,cur)).fetchone()
        if not step:
            raise ValueError('Workflow complete or not available for this ticket')
        db.execute('UPDATE ticket_steps SET status=\'done\' WHERE ticket_id=? AND step_index=?', (ticket_id,cur))
        db.execute('UPDATE vehicles SET workflow_current_step=? WHERE id=?',(cur+1,vehicle_id))
        db.execute("UPDATE ticket_steps SET status='current' WHERE ticket_id=? AND step_index=? AND status='pending'",(ticket_id,cur+1))
        db.execute('INSERT INTO events(vehicle_id,ticket_id,kind,author,body,created_at,is_demo) VALUES (?,?,?,?,?,?,1)',
                  (vehicle_id,ticket_id,'internal','Fleet planner',f'Workflow step completed: {step["label"]}',datetime.now().isoformat(timespec='seconds')))
        db.commit()


def add_contact(name: str, email: str, role: str) -> int:
    if role not in {'internal','external'}:
        raise ValueError('Invalid role')
    with connection() as db:
        existing=db.execute('SELECT id FROM contacts WHERE lower(email)=lower(?)',(email,)).fetchone()
        if existing:
            return int(existing['id'])
        cur=db.execute('INSERT INTO contacts(name,email,role) VALUES(?,?,?)',(name.strip(),email.strip(),role))
        db.commit()
        return int(cur.lastrowid)


def toggle_subscriber(vehicle_id: int, contact_id: int, subscribed: bool) -> None:
    with connection() as db:
        if not db.execute('SELECT 1 FROM vehicles WHERE id=?',(vehicle_id,)).fetchone() or not db.execute('SELECT 1 FROM contacts WHERE id=?',(contact_id,)).fetchone():
            raise ValueError('Vehicle or contact not found')
        db.execute('''INSERT INTO subscriptions(vehicle_id,contact_id,is_subscriber) VALUES(?,?,?)
                      ON CONFLICT(vehicle_id,contact_id) DO UPDATE SET is_subscriber=excluded.is_subscriber''',
                   (vehicle_id,contact_id,1 if subscribed else 0))
        db.commit()
