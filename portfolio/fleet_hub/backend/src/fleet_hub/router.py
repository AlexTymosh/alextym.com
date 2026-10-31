"""Single public API entrypoint for the embedded Fleet VOR Hub project."""

from fastapi import APIRouter

from fleet_hub.api import (
    vor,
    vor_checklist,
    vor_data,
    vor_intake,
    vor_operations,
    vor_reconciliation,
    vor_reporting,
    vor_workflow_admin,
)

router = APIRouter()
for module in (
    vor,
    vor_workflow_admin,
    vor_reporting,
    vor_reconciliation,
    vor_operations,
    vor_checklist,
    vor_data,
    vor_intake,
):
    router.include_router(module.router)
