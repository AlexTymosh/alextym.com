"""Persisted v2-only repair-stage checklists for the synthetic Fleet VOR Hub."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.vor import required, same_origin
from app.services import vor_store, vor_operations as ops

router = APIRouter(prefix="/vor/checklists", tags=["Fleet VOR demo checklists"])
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


class UpdateItem(BaseModel):
    vehicle_id: int = Field(gt=0)
    ticket_id: str = Field(min_length=1, max_length=64)
    step_index: int = Field(ge=0, le=50)
    key: str = Field(min_length=2, max_length=75)
    checked: bool = False
    value: str | None = Field(default=None, max_length=10)


class AdvanceStage(BaseModel):
    vehicle_id: int = Field(gt=0)
    ticket_id: str = Field(min_length=1, max_length=64)


def _init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS vor_step_checklists (
        ticket_id TEXT NOT NULL REFERENCES tickets(id),
        step_index INTEGER NOT NULL,
        item_key TEXT NOT NULL,
        checked INTEGER NOT NULL DEFAULT 0,
        value TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(ticket_id,step_index,item_key)
    )""")


def _assert_ticket(db, vehicle_id: int, ticket_id: str):
    row = db.execute(
        "SELECT id,status,scenario FROM tickets WHERE id=? AND vehicle_id=?",
        (ticket_id, vehicle_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Ticket not found for vehicle")
    return row


@router.get("/{ticket_id}", dependencies=[Depends(required)])
def read_checklist(ticket_id: str):
    with vor_store.connection() as db:
        _init(db)
        if db.execute("SELECT 1 FROM tickets WHERE id=?", (ticket_id,)).fetchone() is None:
            raise HTTPException(404, "Ticket not found")
        rows = db.execute(
            "SELECT step_index,item_key,checked,value FROM vor_step_checklists WHERE ticket_id=?",
            (ticket_id,),
        ).fetchall()
        return {
            "items": [
                {"step_index": r[0], "key": r[1], "checked": bool(r[2]), "value": r[3]}
                for r in rows
            ]
        }


@router.post("", dependencies=[Depends(required)])
def update_item(body: UpdateItem, request: Request):
    same_origin(request)
    if body.step_index >= len(CHECKLIST) or body.key not in CHECKLIST[body.step_index]:
        raise HTTPException(422, "Unknown checklist item")
    if body.key == "diagnosis_date":
        if body.checked:
            try:
                if not body.value or date.fromisoformat(body.value).isoformat() != body.value:
                    raise ValueError()
            except ValueError:
                raise HTTPException(422, "Valid appointment date required") from None
        else:
            body.value = None
    else:
        body.value = None
    with vor_store.connection() as db:
        _init(db)
        ticket = _assert_ticket(db, body.vehicle_id, body.ticket_id)
        if ticket["status"] != "open":
            raise HTTPException(409, "Ticket is not open")
        step = db.execute(
            "SELECT status FROM ticket_steps WHERE ticket_id=? AND step_index=?",
            (body.ticket_id, body.step_index),
        ).fetchone()
        if not step:
            raise HTTPException(404, "Workflow stage not found")
        if step["status"] == "done":
            raise HTTPException(409, "Completed stage is read-only")
        db.execute(
            """INSERT INTO vor_step_checklists(ticket_id,step_index,item_key,checked,value,updated_at)
          VALUES(?,?,?,?,?,?) ON CONFLICT(ticket_id,step_index,item_key)
          DO UPDATE SET checked=excluded.checked,value=excluded.value,updated_at=excluded.updated_at""",
            (
                body.ticket_id,
                body.step_index,
                body.key,
                int(body.checked),
                body.value,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        db.commit()
        return {"ok": True}


@router.post("/advance", dependencies=[Depends(required)])
def advance_with_checks(body: AdvanceStage, request: Request):
    same_origin(request)
    with vor_store.connection() as db:
        _init(db)
        ticket = _assert_ticket(db, body.vehicle_id, body.ticket_id)
        if ticket["status"] != "open":
            raise HTTPException(409, "Ticket is not open")
        step = db.execute(
            "SELECT step_index FROM ticket_steps WHERE ticket_id=? AND status='current'",
            (body.ticket_id,),
        ).fetchone()
        if step is None:
            raise HTTPException(409, "No current stage")
        index = int(step[0])
        if index < len(CHECKLIST):
            completed = {
                r[0]
                for r in db.execute(
                    "SELECT item_key FROM vor_step_checklists WHERE ticket_id=? AND step_index=? AND checked=1",
                    (body.ticket_id, index),
                )
            }
            pending = (
                set()
                if str(ticket["scenario"]).startswith("custom_")
                else ops.required_keys(db, index)
            ) - completed
            if pending:
                raise HTTPException(409, "Complete the current stage checklist before advancing")
    # Standard store method advances and audits the workflow. No vehicle status is changed.
    try:
        vor_store.advance_workflow(body.vehicle_id, body.ticket_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True}


# PR14 CUSTOM WORKFLOW GATE: user-defined stage labels have no mandatory legacy checklist items.
