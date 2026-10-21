"""Synthetic Fleet VOR v2 defect intake. Never writes to HOTH or KEY2.

A defect creates a case and a linked PTS tracking ticket, but never updates
vehicle availability. Specialist work remains with the HOTH-owned team.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import UUID

from app.services import vor_data

PATHWAYS = {"standard", "tyres", "windscreen"}
SOURCES = {"outlook", "manual"}
REASONS = {
    "Mechanical",
    "Accident Repair",
    "Warranty",
    "Equipment",
    "Missed Event(s)",
    "Unknown / Under Investigation",
}
STEPS = [
    "Service company notified — awaiting acknowledgement",
    "Initial diagnosis scheduled — awaiting findings",
    "Awaiting quotation",
    "Repair approval",
    "Repair in progress",
    "Repair completed — release checklist",
    "HOTH closure notification",
    "Post-repair documentation",
]
SCENARIOS = {
    "standard": ("standard_defect_v2", "Standard Defect — PTS Fleet", STEPS),
    "tyres": ("hoth_tyres_v2", "Wheels / Tyres — HOTH managed", []),
    "windscreen": ("hoth_windscreen_v2", "Windscreen — HOTH managed", []),
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def migrate(db) -> None:
    """Apply additive intake columns after PR-02 has ensured vor_cases exists."""
    names = {row[1] for row in db.execute("PRAGMA table_info(vor_cases)")}
    for name, clause in {
        "intake_request_id": "TEXT",
        "reported_vor": "INTEGER NOT NULL DEFAULT 0",
        "roadside_reported": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        if name not in names:
            db.execute(f"ALTER TABLE vor_cases ADD COLUMN {name} {clause}")
    db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_vor_cases_intake_request
                  ON vor_cases(intake_request_id) WHERE intake_request_id IS NOT NULL""")
    for code, name, steps in SCENARIOS.values():
        db.execute(
            "INSERT OR IGNORE INTO workflow_templates(code,name,steps_json) VALUES(?,?,?)",
            (code, name, json.dumps(steps)),
        )
    db.commit()


def list_for_intake() -> dict:
    with vor_data.database() as db:
        migrate(db)
        vehicles = db.execute("""SELECT id,registration,model,garage,availability_status,is_archived
                                 FROM vehicles ORDER BY registration""").fetchall()
        return {
            "vehicles": [dict(row) for row in vehicles],
            "reasons": sorted(REASONS),
            "pathways": ["standard", "tyres", "windscreen"],
        }


def _ticket_id(db) -> str:
    """Use the seeded PS000xxx numbering without making any external HOTH claim."""
    values = [
        int(match.group(1))
        for row in db.execute("SELECT id FROM tickets WHERE id LIKE 'PS%'")
        if (match := re.fullmatch(r"PS(\d+)", row[0])) is not None
    ]
    return f"PS{max(values, default=0) + 1:06d}"


def register_defect(
    *, vehicle_id: int, pathway: str, reason: str, description: str,
    hoth_reference: str, source: str, reported_vor: bool, roadside_reported: bool,
    request_id: str,
) -> dict:
    if pathway not in PATHWAYS:
        raise ValueError("Select a valid defect pathway")
    if reason not in REASONS:
        raise ValueError("Select a valid high-level VOR reason")
    if source not in SOURCES:
        raise ValueError("Invalid notification source")
    if not 3 <= len(description.strip()) <= 2000:
        raise ValueError("Description must be 3–2,000 characters")
    if not 2 <= len(hoth_reference.strip()) <= 80:
        raise ValueError("HOTH reference is required (2–80 characters)")
    try:
        request_id = str(UUID(request_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("Invalid request identifier") from exc

    with vor_data.database() as db:
        migrate(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            previous = db.execute(
                """SELECT id,legacy_ticket_id,vehicle_id,pathway,description,vor_reason,
                          hoth_reference,source,reported_vor,roadside_reported
                   FROM vor_cases WHERE intake_request_id=?""",
                (request_id,),
            ).fetchone()
            if previous:
                if (
                    int(previous["vehicle_id"]) != vehicle_id
                    or previous["pathway"] != pathway
                    or previous["description"] != description.strip()
                    or previous["vor_reason"] != reason
                    or previous["hoth_reference"] != hoth_reference.strip()
                    or previous["source"] != source
                    or bool(previous["reported_vor"]) != reported_vor
                    or bool(previous["roadside_reported"]) != roadside_reported
                ):
                    raise ValueError("Request identifier reused for a different defect")
                db.commit()
                return {
                    "case_id": previous["id"], "ticket_id": previous["legacy_ticket_id"],
                    "repeated": True, "availability_changed": False,
                }
            vehicle = db.execute(
                "SELECT id,registration,is_archived FROM vehicles WHERE id=?", (vehicle_id,)
            ).fetchone()
            if vehicle is None:
                raise ValueError("Vehicle does not exist in the Fleet Register")
            if vehicle["is_archived"]:
                raise ValueError("Restore the archived vehicle before registering a defect")
            # One HOTH reference represents one open notification per vehicle.
            if db.execute(
                """SELECT id FROM vor_cases
                   WHERE vehicle_id=? AND upper(trim(hoth_reference))=upper(?) AND status='open'""",
                (vehicle_id, hoth_reference.strip()),
            ).fetchone():
                raise ValueError("An open defect with this HOTH reference already exists")
            # Distinct cases per vehicle are allowed; duplicate form submits are not.
            code, label, steps = SCENARIOS[pathway]
            ticket = _ticket_id(db)
            created = now_utc()
            db.execute(
                """INSERT INTO tickets
                (id,vehicle_id,kind,title,status,severity,scenario,opened_at,closed_at,
                 key2_reference,hoth_reference,is_demo)
                VALUES(?,?,? ,?,'open','Medium',?,?,NULL,NULL,?,1)""",
                (ticket, vehicle_id, "DEFECT" if pathway == "standard" else "EXTERNAL",
                 description.strip(), code, created, hoth_reference.strip()),
            )
            if steps:
                db.executemany(
                    """INSERT INTO ticket_steps(ticket_id,step_index,label,status)
                       VALUES(?,?,?,?)""",
                    [(ticket, i, step, "current" if i == 0 else "pending")
                     for i, step in enumerate(steps)],
                )
            cur = db.execute(
                """INSERT INTO vor_cases
                   (vehicle_id,legacy_ticket_id,pathway,description,vor_reason,source,
                    hoth_reference,opened_at,closed_at,status,created_at,intake_request_id,
                    reported_vor,roadside_reported)
                   VALUES(?,?,?,?,?,?,?,?,NULL,'open',?,?,?,?)""",
                (vehicle_id, ticket, pathway, description.strip(), reason, source,
                 hoth_reference.strip(), created, created, request_id,
                 int(reported_vor), int(roadside_reported)),
            )
            # Display latest defect in the current workspace. NO KEY2 or VOR state update.
            next_action = (
                "Awaiting service company acknowledgement" if pathway == "standard"
                else "HOTH team manages repair — PTS Fleet monitors status"
            )
            db.execute(
                """UPDATE vehicles SET issue=?,scenario=?,workflow_current_step=0,next_action=?
                   WHERE id=?""",
                (description.strip(), code, next_action, vehicle_id),
            )
            db.execute(
                """INSERT INTO events(vehicle_id,ticket_id,kind,author,body,created_at,is_demo)
                   VALUES(?,?,'internal','Fleet Hub',?,?,1)""",
                (vehicle_id, ticket,
                 f"Defect received via {source}. HOTH: {hoth_reference.strip()}. "
                 f"Pathway: {label}. Reason: {reason}. "
                 f"Reported VOR: {'Yes' if reported_vor else 'No'}. "
                 f"Roadside: {'Yes (separate process)' if roadside_reported else 'No'}. "
                 "KEY2 status unchanged; any update requires explicit Fleet confirmation.",
                 created),
            )
            db.commit()
            return {
                "case_id": int(cur.lastrowid), "ticket_id": ticket,
                "repeated": False, "availability_changed": False,
                "registration": vehicle["registration"],
                "pathway": pathway, "requires_pts_workflow": bool(steps),
            }
        except Exception:
            db.rollback()
            raise
