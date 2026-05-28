from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.rate_limit import enforce_escalation_rate_limit
from app.core.config import Settings, get_settings
from app.schemas.escalation import EscalationRequest, EscalationResponse
from app.services.escalation import (
    EscalationConfigurationError,
    EscalationDeliveryError,
    EscalationService,
)

router = APIRouter(tags=["escalation"])


def get_escalation_service(settings: Settings = Depends(get_settings)) -> EscalationService:
    return EscalationService.from_settings(settings)


@router.post("/escalations", response_model=EscalationResponse)
async def escalate(
    escalation_request: EscalationRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: EscalationService = Depends(get_escalation_service),
) -> EscalationResponse:
    if not escalation_request.is_honeypot_filled:
        enforce_escalation_rate_limit(request, settings)

    try:
        return await service.submit(escalation_request)
    except EscalationConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Escalation is not configured.",
        ) from exc
    except EscalationDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect with Alex. Please try again later.",
        ) from exc
