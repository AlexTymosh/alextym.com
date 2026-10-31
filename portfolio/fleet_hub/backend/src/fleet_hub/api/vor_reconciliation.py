"""Protected demo reconciliation API for HOTH and Fleet data snapshots (v2 only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from fleet_hub.api.vor import required, same_origin
from fleet_hub.services import vor_reconciliation as recon

router = APIRouter(
    prefix="/vor/reconciliation", tags=["Fleet reconciliation"], dependencies=[Depends(required)]
)


class ImportSnapshot(BaseModel):
    source: str = Field(min_length=4, max_length=5)
    label: str = Field(min_length=1, max_length=100)
    source_as_of: str = Field(min_length=20, max_length=35)
    csv_text: str = Field(min_length=5, max_length=550_000)


class Compare(BaseModel):
    hoth_batch_id: int | None = Field(default=None, gt=0)
    fleet_batch_id: int | None = Field(default=None, gt=0)


class Review(BaseModel):
    issue_id: int = Field(gt=0)
    decision: str = Field(min_length=4, max_length=30)
    actor: str = Field(min_length=2, max_length=100)
    owner: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=750)


def safe(fn):
    try:
        return fn()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/batches")
def batches():
    return safe(recon.batches)


@router.post("/imports")
def upload(body: ImportSnapshot, request: Request):
    same_origin(request)
    return safe(lambda: recon.upload(body.source, body.csv_text, body.label, body.source_as_of))


@router.post("/compare")
def compare(body: Compare, request: Request):
    same_origin(request)
    return safe(lambda: recon.compare(body.hoth_batch_id, body.fleet_batch_id))


@router.get("/runs")
def runs():
    return safe(recon.runs)


@router.get("/latest")
def latest(run_id: int | None = None):
    return safe(lambda: recon.detail(run_id))


@router.post("/review")
def review(body: Review, request: Request):
    same_origin(request)
    return safe(
        lambda: recon.review(body.issue_id, body.decision, body.actor, body.owner, body.note)
    )


@router.get("/export.xlsx")
def export(run_id: int):
    payload = safe(lambda: recon.export_xlsx(run_id))
    return Response(
        payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="fleet-reconciliation-{run_id}.xlsx"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/export.csv")
def export_csv(run_id: int):
    payload = safe(lambda: recon.export_csv(run_id))
    return Response(
        payload,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="fleet-reconciliation-{run_id}.csv"',
            "Cache-Control": "no-store",
        },
    )
