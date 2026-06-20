from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.rate_limit import (
    enforce_escalation_message_rate_limit,
    enforce_escalation_rate_limit,
)
from app.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, serialize_sse_item, sse_event
from app.core.config import Settings, get_settings
from app.core.domain_metrics import record_escalation_event
from app.core.project_config import get_project_config
from app.schemas.escalation import (
    EscalationCloseResponse,
    EscalationMessageRequest,
    EscalationMessageResponse,
    EscalationRequest,
    EscalationResponse,
)
from app.services.escalation import (
    EscalationConfigurationError,
    EscalationDeliveryError,
    EscalationNotFoundError,
    EscalationService,
)
from app.services.handoff_availability import HandoffUnavailableError

router = APIRouter(tags=["escalation"])
_OWNER_REFERENCE = get_project_config().assistant.owner_reference


def get_escalation_service(
    settings: Settings = Depends(get_settings),
) -> EscalationService:
    return EscalationService.from_settings(settings)


@router.post(
    "/escalations",
    response_model=EscalationResponse,
    response_model_exclude_none=True,
)
async def escalate(
    escalation_request: EscalationRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: EscalationService = Depends(get_escalation_service),
) -> EscalationResponse:
    if escalation_request.is_honeypot_filled:
        response = await service.submit(escalation_request)
        record_escalation_event(action="create", outcome="honeypot")
        return response

    try:
        _ensure_handoff_available(service)
        enforce_escalation_rate_limit(request, settings)
        response = await service.submit(escalation_request)
    except HandoffUnavailableError as exc:
        record_escalation_event(action="create", outcome="unavailable")
        raise _handoff_unavailable_http_exception(exc) from exc
    except EscalationConfigurationError as exc:
        record_escalation_event(action="create", outcome="configuration_error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Escalation is not configured.",
        ) from exc
    except EscalationDeliveryError as exc:
        record_escalation_event(action="create", outcome="delivery_error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not connect with {_OWNER_REFERENCE}. Please try again later.",
        ) from exc

    record_escalation_event(action="create", outcome="success")
    return response


@router.post(
    "/escalations/{handoff_id}/messages",
    response_model=EscalationMessageResponse,
)
async def send_escalation_message(
    handoff_id: str,
    message_request: EscalationMessageRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: EscalationService = Depends(get_escalation_service),
) -> EscalationMessageResponse:
    if message_request.is_honeypot_filled:
        record_escalation_event(action="message", outcome="honeypot")
        return EscalationMessageResponse()

    try:
        enforce_escalation_message_rate_limit(request, settings)
        response = await service.submit_user_message(handoff_id, message_request)
    except EscalationConfigurationError as exc:
        record_escalation_event(action="message", outcome="configuration_error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Escalation messaging is not configured.",
        ) from exc
    except EscalationNotFoundError as exc:
        record_escalation_event(action="message", outcome="not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation session was not found.",
        ) from exc
    except EscalationDeliveryError as exc:
        record_escalation_event(action="message", outcome="delivery_error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not send this message to {_OWNER_REFERENCE}. Please try again later.",
        ) from exc

    record_escalation_event(action="message", outcome="success")
    return response


@router.post(
    "/escalations/{handoff_id}/close",
    response_model=EscalationCloseResponse,
)
async def close_escalation(
    handoff_id: str,
    service: EscalationService = Depends(get_escalation_service),
) -> EscalationCloseResponse:
    try:
        response = await service.close(handoff_id)
    except EscalationConfigurationError as exc:
        record_escalation_event(action="close", outcome="configuration_error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Escalation session storage is not configured.",
        ) from exc
    except EscalationNotFoundError as exc:
        record_escalation_event(action="close", outcome="not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation session was not found.",
        ) from exc
    except EscalationDeliveryError as exc:
        record_escalation_event(action="close", outcome="delivery_error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not close this handoff. Please try again later.",
        ) from exc

    record_escalation_event(action="close", outcome="success")
    return response


@router.get("/escalations/{handoff_id}/stream")
async def stream_escalation_messages(
    handoff_id: str,
    request: Request,
    last_event_id: Annotated[
        str | None,
        Header(alias="Last-Event-ID"),
    ] = None,
    service: EscalationService = Depends(get_escalation_service),
) -> StreamingResponse:
    try:
        await service.ensure_stream_available(handoff_id)
    except EscalationConfigurationError as exc:
        record_escalation_event(action="stream", outcome="configuration_error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Escalation streaming is not configured.",
        ) from exc
    except EscalationNotFoundError as exc:
        record_escalation_event(action="stream", outcome="not_found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation session was not found.",
        ) from exc
    except EscalationDeliveryError as exc:
        record_escalation_event(action="stream", outcome="delivery_error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Escalation stream could not be opened.",
        ) from exc

    record_escalation_event(action="stream", outcome="opened")

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in service.stream_alex_messages(
                handoff_id,
                after_message_id=last_event_id,
            ):
                if await request.is_disconnected():
                    record_escalation_event(
                        action="stream",
                        outcome="disconnected",
                    )
                    break
                yield serialize_sse_item(event)
        except EscalationDeliveryError:
            record_escalation_event(action="stream", outcome="delivery_error")
            yield sse_event(
                "error",
                {"message": "Escalation stream is temporarily unavailable."},
            )

    return StreamingResponse(
        event_generator(),
        media_type=SSE_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )


def _ensure_handoff_available(service: EscalationService) -> None:
    service.ensure_handoff_available()


def _handoff_unavailable_http_exception(
    exc: HandoffUnavailableError,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=exc.status.to_http_detail(),
    )
