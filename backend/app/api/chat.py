from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.rate_limit import enforce_chat_rate_limit
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


def get_chat_service() -> ChatService:
    return ChatService()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    chat_request: ChatRequest,
    _: None = Depends(enforce_chat_rate_limit),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return service.answer(chat_request)


@router.post("/chat/stream")
async def chat_stream(
    chat_request: ChatRequest,
    request: Request,
    _: None = Depends(enforce_chat_rate_limit),
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in service.stream_answer(chat_request):
                if await request.is_disconnected():
                    break
                yield event
        except Exception:
            yield ChatService._sse_event(
                "error",
                {"message": "Something went wrong. Please try again later."},
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
