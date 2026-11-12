"""Persisted v2-only repair-stage checklists for the synthetic Fleet VOR Hub."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from fleet_hub.api.dependencies import required, same_origin
from fleet_hub.services import vor_store
from fleet_hub.services import vor_checklist_advance as checklist_service

router = APIRouter(prefix="/vor/checklists", tags=["Fleet VOR demo checklists"])
CHECKLIST = checklist_service.CHECKLIST


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
    checklist_service.ensure_checklist_table(db)


def _assert_ticket(db, vehicle_id: int, ticket_id: str):
    try:
        return checklist_service.ticket_for_vehicle(db, vehicle_id, ticket_id)
    except checklist_service.ChecklistAdvanceError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc


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
    try:
        return checklist_service.advance_with_checks(body.vehicle_id, body.ticket_id)
    except checklist_service.ChecklistAdvanceError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc


# PR14 CUSTOM WORKFLOW GATE: user-defined stage labels have no mandatory legacy checklist items.
