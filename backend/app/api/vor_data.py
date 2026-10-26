"""Authenticated v2 vehicle register and CSV/XLSX import endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.vor import required, same_origin
from app.services import vor_data

router = APIRouter(prefix="/vor/data", tags=["Fleet VOR v2 data"], dependencies=[Depends(required)])


class ManualVehicle(BaseModel):
    registration: str = Field(min_length=2, max_length=32)
    model: str = Field(min_length=1, max_length=120)
    garage: str = Field(min_length=1, max_length=100)


class ArchiveVehicle(BaseModel):
    archived: bool


class ManualStatus(BaseModel):
    status: str
    actor: str = Field(default="Fleet Department", min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=250)
    reference: str = Field(default="", max_length=100)


class Upload(BaseModel):
    filename: str = Field(min_length=5, max_length=180)
    content_b64: str = Field(min_length=1, max_length=2_800_000)
    mode: str = Field(default="skip")
    digest: str | None = Field(default=None, max_length=64)


def response_or_bad_request(callback):
    try:
        return callback()
    except ValueError:
        # Do not expose database paths, parser internals or exception chaining.
        raise HTTPException(status_code=400, detail="Invalid fleet data request") from None
    except RuntimeError:
        # Includes the v1/v2 isolation guard; keep internal configuration private.
        raise HTTPException(status_code=503, detail="Fleet data service unavailable") from None


@router.get("/register")
def list_register(include_archived: bool = True):
    return response_or_bad_request(lambda: vor_data.register_list(include_archived))


@router.post("/vehicles")
def create_vehicle(body: ManualVehicle, request: Request):
    same_origin(request)
    return response_or_bad_request(
        lambda: vor_data.register_vehicle(body.registration, body.model, body.garage)
    )


@router.post("/vehicles/{vehicle_id}/archive")
def set_archive(vehicle_id: int, body: ArchiveVehicle, request: Request):
    same_origin(request)
    return response_or_bad_request(lambda: vor_data.archive_vehicle(vehicle_id, body.archived))


@router.post("/vehicles/{vehicle_id}/status")
def set_status(vehicle_id: int, body: ManualStatus, request: Request):
    same_origin(request)
    return response_or_bad_request(
        lambda: vor_data.update_status(
            vehicle_id, body.status, body.actor, body.reason, body.reference
        )
    )


@router.post("/imports/preview")
def import_preview(body: Upload, request: Request):
    same_origin(request)
    return response_or_bad_request(
        lambda: vor_data.prepare_import(body.filename, body.content_b64, body.mode)
    )


@router.post("/imports/commit")
def import_commit(body: Upload, request: Request):
    same_origin(request)
    if not body.digest or len(body.digest) != 64:
        raise HTTPException(400, "An expected SHA-256 digest is required")
    return response_or_bad_request(
        lambda: vor_data.commit_import(body.filename, body.content_b64, body.mode, body.digest)
    )
