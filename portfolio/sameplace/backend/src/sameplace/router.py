"""Public host entrypoint; authorization is injected by the composition root."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/sameplace", tags=["sameplace"])


class FoundationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = "sameplace"
    stage: str = "foundation"
    contract_version: int = 1


@router.get("/status", response_model=FoundationStatus, include_in_schema=False)
def foundation_status() -> FoundationStatus:
    """No identity details, game state, database reads or side effects."""
    return FoundationStatus()
