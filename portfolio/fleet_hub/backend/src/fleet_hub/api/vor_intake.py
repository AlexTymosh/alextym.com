"""Protected synthetic defect-intake endpoints for Fleet VOR Hub v2 only."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from fleet_hub.api.vor import required, same_origin
from fleet_hub.services import vor_intake

router = APIRouter(
    prefix="/vor/intake", tags=["Fleet VOR v2 intake"], dependencies=[Depends(required)]
)


class DefectIntake(BaseModel):
    vehicle_id: int = Field(gt=0)
    pathway: Literal["standard", "tyres", "windscreen"]
    reason: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=3, max_length=2000)
    hoth_reference: str = Field(min_length=2, max_length=80)
    source: Literal["outlook", "manual"] = "outlook"
    reported_vor: bool = False
    roadside_reported: bool = False
    request_id: str = Field(min_length=36, max_length=36)


@router.get("/options")
def options():
    try:
        return vor_intake.list_for_intake()
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/defects", status_code=201)
def create(body: DefectIntake, request: Request):
    same_origin(request)
    try:
        return vor_intake.register_defect(**body.model_dump())
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
