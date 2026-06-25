from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.rate_limit import enforce_chat_rate_limit
from app.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, serialize_sse_item, sse_event
from app.core.config import Settings, get_settings
from app.core.domain_metrics import record_chat_request
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_metrics import MetricsChatService, build_metrics_chat_service

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["chat"])


def get_chat_service(
    settings: Settings = Depends(get_settings),
) -> MetricsChatService:
    return build_metrics_chat_service(settings)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    chat_request: ChatRequest,
    _: None = Depends(enforce_chat_rate_limit),
    service: MetricsChatService = Depends(get_chat_service),
) -> ChatResponse:
    return service.answer(chat_request)


@router.post("/chat/stream")
async def chat_stream(
    chat_request: ChatRequest,
    request: Request,
    _: None = Depends(enforce_chat_rate_limit),
    service: MetricsChatService = Depends(get_chat_service),
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in service.stream_answer(chat_request):
                if await request.is_disconnected():
                    logger.info(
                        "chat.stream.disconnected",
                        message="Chat stream client disconnected.",
                    )
                    record_chat_request(
                        mode="stream",
                        outcome="disconnected",
                        policy_intent="none",
                    )
                    break
                yield serialize_sse_item(event)
        except Exception as exc:
            logger.exception(
                "chat.stream.failed",
                message="Chat stream failed.",
                error_type=type(exc).__name__,
            )
            yield sse_event(
                "error",
                {"message": "Something went wrong. Please try again later."},
            )

    return StreamingResponse(
        event_generator(),
        media_type=SSE_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )
