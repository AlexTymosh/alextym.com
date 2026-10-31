"""Authenticated CRUD for V2 repair workflow templates."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from fleet_hub.api.vor import required, same_origin
from fleet_hub.services import vor_workflow_admin as service

router = APIRouter(
    prefix="/vor/workflow-admin",
    tags=["Fleet VOR workflow library"],
    dependencies=[Depends(required)],
)


class Create(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    first_stage: str = Field(min_length=3, max_length=100)


class Rename(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=3, max_length=100)


class Stage(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    label: str = Field(min_length=3, max_length=100)


class EditStage(Stage):
    index: int = Field(ge=0, le=31)


class DeleteStage(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    index: int = Field(ge=0, le=31)


class DeleteWorkflow(BaseModel):
    code: str = Field(min_length=2, max_length=64)


def call(operation):
    try:
        return operation()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("")
def catalogue():
    return call(service.catalogue)


@router.post("/create")
def create(body: Create, request: Request):
    same_origin(request)
    return call(lambda: service.create(body.name, body.first_stage))


@router.post("/rename")
def rename(body: Rename, request: Request):
    same_origin(request)
    return call(lambda: service.rename(body.code, body.name))


@router.post("/stage/add")
def add_stage(body: Stage, request: Request):
    same_origin(request)
    return call(lambda: service.add_stage(body.code, body.label))


@router.post("/stage/edit")
def edit_stage(body: EditStage, request: Request):
    same_origin(request)
    return call(lambda: service.change_stage(body.code, body.index, body.label))


@router.post("/stage/delete")
def delete_stage(body: DeleteStage, request: Request):
    same_origin(request)
    return call(lambda: service.remove_stage(body.code, body.index))


@router.post("/delete")
def delete_workflow(body: DeleteWorkflow, request: Request):
    same_origin(request)
    return call(lambda: service.remove_workflow(body.code))
