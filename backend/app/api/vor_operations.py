"""Authenticated v2 Fleet operational-control API. No external system writes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from app.api.vor import required, same_origin
from app.services import vor_operations as ops

router = APIRouter(
    prefix="/vor/ops", tags=["Fleet operational controls"], dependencies=[Depends(required)]
)


class CaseRef(BaseModel):
    vehicle_id: int = Field(gt=0)
    ticket_id: str = Field(min_length=1, max_length=64)


class NewAction(CaseRef):
    title: str = Field(min_length=3, max_length=220)
    owner: str = Field(min_length=2, max_length=100)
    due_at: str = Field(min_length=10, max_length=10)


class RecordId(CaseRef):
    id: int = Field(gt=0)


class NewBlocker(CaseRef):
    kind: str = Field(min_length=2, max_length=60)
    detail: str = Field(min_length=3, max_length=500)


class NewDocument(CaseRef):
    kind: str = Field(min_length=2, max_length=60)
    reference: str = Field(default="", max_length=180)
    status: str = Field(default="missing", max_length=30)


class UpdateDocument(RecordId):
    status: str = Field(max_length=30)


class ReleaseItem(CaseRef):
    key: str = Field(min_length=2, max_length=100)
    checked: bool


class ManualStatus(CaseRef):
    new_status: str
    reason: str = Field(min_length=5, max_length=400)
    confirmed: bool = False
    override_incomplete_release: bool = False


class SkipStage(CaseRef):
    actor: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=8, max_length=400)


class UpdateTemplate(BaseModel):
    stage_index: int = Field(ge=0, le=7)
    key: str = Field(min_length=2, max_length=75)
    label: str = Field(min_length=3, max_length=100)
    required: bool


def safe(call):
    try:
        return call()
    except (ValueError, RuntimeError) as e:
        raise HTTPException(409, str(e)) from e


@router.get("/overview")
def overview():
    return safe(ops.overview)


@router.get("/queue")
def queue():
    return safe(ops.queue)


@router.get("/templates")
def templates():
    return safe(ops.templates)


@router.get("/details")
def details(vehicle_id: int, ticket_id: str):
    return safe(lambda: ops.details(vehicle_id, ticket_id))


@router.post("/actions")
def add_action(body: NewAction, request: Request):
    same_origin(request)
    return safe(
        lambda: ops.add_action(body.vehicle_id, body.ticket_id, body.title, body.owner, body.due_at)
    )


@router.post("/actions/complete")
def complete_action(body: RecordId, request: Request):
    same_origin(request)
    return safe(lambda: ops.complete_action(body.vehicle_id, body.ticket_id, body.id))


@router.post("/blockers")
def add_blocker(body: NewBlocker, request: Request):
    same_origin(request)
    return safe(lambda: ops.add_blocker(body.vehicle_id, body.ticket_id, body.kind, body.detail))


@router.post("/blockers/resolve")
def resolve_blocker(body: RecordId, request: Request):
    same_origin(request)
    return safe(lambda: ops.resolve_blocker(body.vehicle_id, body.ticket_id, body.id))


@router.post("/documents")
def add_document(body: NewDocument, request: Request):
    same_origin(request)
    return safe(
        lambda: ops.add_document(
            body.vehicle_id, body.ticket_id, body.kind, body.reference, body.status
        )
    )


@router.post("/documents/status")
def update_document(body: UpdateDocument, request: Request):
    same_origin(request)
    return safe(lambda: ops.update_document(body.vehicle_id, body.ticket_id, body.id, body.status))


@router.post("/release")
def release(body: ReleaseItem, request: Request):
    same_origin(request)
    return safe(lambda: ops.release_check(body.vehicle_id, body.ticket_id, body.key, body.checked))


@router.post("/status")
def status(body: ManualStatus, request: Request):
    same_origin(request)
    return safe(
        lambda: ops.confirm_status(
            body.vehicle_id,
            body.ticket_id,
            body.new_status,
            body.reason,
            body.confirmed,
            body.override_incomplete_release,
        )
    )


@router.post("/skip")
def skip(body: SkipStage, request: Request):
    same_origin(request)
    return safe(lambda: ops.skip_stage(body.vehicle_id, body.ticket_id, body.actor, body.reason))


@router.post("/templates")
def update_template(body: UpdateTemplate, request: Request):
    same_origin(request)
    return safe(lambda: ops.update_template(body.stage_index, body.key, body.label, body.required))
