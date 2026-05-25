import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.schemas.chat import ChatRequest, ChatResponse

INSUFFICIENT_DATA_ANSWER = (
    "I do not have enough reliable information in Alex's public knowledge base to answer that "
    "accurately."
)

PROMPT_INJECTION_ANSWER = (
    "I can't help reveal or override hidden instructions, system prompts, or system "
    "configuration. I can answer professional questions about Alex when reliable public knowledge "
    "is available."
)

PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "reveal your system prompt",
    "show your system prompt",
    "display your system prompt",
    "print your system prompt",
    "hidden instructions",
    "developer instructions",
    "system instructions",
    "show hidden context",
    "dump all documents",
    "dump the knowledge base",
    "show api keys",
    "reveal api keys",
    "bypass rules",
    "pretend you know",
    "answer without context",
)


class ChatService:
    def answer(self, request: ChatRequest) -> ChatResponse:
        if self._looks_like_prompt_injection(request.message):
            return ChatResponse(
                answer=PROMPT_INJECTION_ANSWER,
                sources=[],
                confidence="low",
                not_enough_data=True,
            )

        return ChatResponse(
            answer=INSUFFICIENT_DATA_ANSWER,
            sources=[],
            confidence="low",
            not_enough_data=True,
        )

    async def stream_answer(self, request: ChatRequest) -> AsyncIterator[str]:
        request_id = str(uuid.uuid4())
        response = self.answer(request)

        yield self._sse_event("meta", {"request_id": request_id, "status": "started"})

        for token in self._tokenize(response.answer):
            yield self._sse_event("token", {"text": token})
            await asyncio.sleep(0)

        yield self._sse_event(
            "sources",
            {"sources": [source.model_dump() for source in response.sources]},
        )
        yield self._sse_event(
            "done",
            {
                "request_id": request_id,
                "confidence": response.confidence,
                "not_enough_data": response.not_enough_data,
            },
        )

    @staticmethod
    def _looks_like_prompt_injection(message: str) -> bool:
        normalized_message = " ".join(message.lower().split())
        return any(pattern in normalized_message for pattern in PROMPT_INJECTION_PATTERNS)

    @staticmethod
    def _tokenize(answer: str) -> list[str]:
        words = answer.split(" ")
        tokens = [words[0]] if words else []
        tokens.extend(f" {word}" for word in words[1:])
        return tokens

    @staticmethod
    def _sse_event(event: str, data: dict[str, Any]) -> str:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return f"event: {event}\ndata: {payload}\n\n"
