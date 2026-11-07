"""Shared Fleet checklist-gated stage advancement, independent of HTTP routers.

Keep the existing SQLite checklist gate and workflow advancement semantics.
HTTP adapters own authentication, origin checks, validation and error mapping.
"""

from __future__ import annotations

from fleet_hub.services import vor_operations as ops
from fleet_hub.services import vor_store

CHECKLIST: tuple[tuple[str, ...], ...] = (
    ("notification_sent", "response_received"),
    (
        "information_forwarded",
        "visit_date_agreed",
        "maintenance_combination_reviewed",
        "diagnosis_date",
    ),
    ("inspected", "initial_quote_received", "preliminary_estimate_confirmed"),
    ("approval_recorded",),
    ("work_started", "repair_finished"),
    ("repair_verified", "release_checked"),
    ("hoth_informed", "hoth_closed_confirmed"),
    ("documents_received", "documents_checked"),
)


class ChecklistAdvanceError(Exception):
    """Checklist / workflow rejection for translation by the HTTP adapters."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def ensure_checklist_table(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS vor_step_checklists (
        ticket_id TEXT NOT NULL REFERENCES tickets(id),
        step_index INTEGER NOT NULL,
        item_key TEXT NOT NULL,
        checked INTEGER NOT NULL DEFAULT 0,
        value TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(ticket_id,step_index,item_key)
    )""")


def ticket_for_vehicle(db, vehicle_id: int, ticket_id: str):
    row = db.execute(
        "SELECT id,status,scenario FROM tickets WHERE id=? AND vehicle_id=?",
        (ticket_id, vehicle_id),
    ).fetchone()
    if row is None:
        raise ChecklistAdvanceError(404, "Ticket not found for vehicle")
    return row


def advance_with_checks(vehicle_id: int, ticket_id: str) -> dict[str, bool]:
    """Advance the workflow only when the current checklist is complete.

    Deliberately use the same two operations and status messages as the old
    /vor/checklists/advance implementation. This does NOT change the vehicle's
    availability status, seed, or SQLite schema.
    """
    with vor_store.connection() as db:
        ensure_checklist_table(db)
        ticket = ticket_for_vehicle(db, vehicle_id, ticket_id)
        if ticket["status"] != "open":
            raise ChecklistAdvanceError(409, "Ticket is not open")
        step = db.execute(
            "SELECT step_index FROM ticket_steps WHERE ticket_id=? AND status='current'",
            (ticket_id,),
        ).fetchone()
        if step is None:
            raise ChecklistAdvanceError(409, "No current stage")
        index = int(step[0])
        if index < len(CHECKLIST):
            completed = {
                r[0]
                for r in db.execute(
                    "SELECT item_key FROM vor_step_checklists WHERE ticket_id=? AND step_index=? AND checked=1",
                    (ticket_id, index),
                )
            }
            pending = (
                set()
                if str(ticket["scenario"]).startswith("custom_")
                else ops.required_keys(db, index)
            ) - completed
            if pending:
                raise ChecklistAdvanceError(
                    409, "Complete the current stage checklist before advancing"
                )

    # Standard store method advances and audits the workflow; no vehicle status change.
    try:
        vor_store.advance_workflow(vehicle_id, ticket_id)
    except ValueError as exc:
        raise ChecklistAdvanceError(409, str(exc)) from exc
    return {"ok": True}
