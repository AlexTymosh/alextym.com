from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.rate_limit import enforce_contact_rate_limit
from app.core.config import Settings, get_settings
from app.core.domain_metrics import record_contact_submission
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.contact import ContactConfigurationError, ContactDeliveryError
from app.services.contact import ContactService

router = APIRouter(tags=["contact"])


def get_contact_service(settings: Settings = Depends(get_settings)) -> ContactService:
    return ContactService.from_settings(settings)


@router.post("/contact", response_model=ContactResponse)
async def contact(
    contact_request: ContactRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: ContactService = Depends(get_contact_service),
) -> ContactResponse:
    if contact_request.is_honeypot_filled:
        response = await service.submit(contact_request)
        record_contact_submission("honeypot")
        return response

    enforce_contact_rate_limit(request, settings)

    try:
        response = await service.submit(contact_request)
    except ContactConfigurationError as exc:
        record_contact_submission("configuration_error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Contact form is not configured.",
        ) from exc
    except ContactDeliveryError as exc:
        record_contact_submission("delivery_error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not send message. Please try again later.",
        ) from exc

    record_contact_submission("success")
    return response
