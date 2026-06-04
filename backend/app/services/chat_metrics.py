from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator

from app.core.config import Settings
from app.core.domain_metrics import (
    elapsed_seconds,
    record_chat_policy_decision,
    record_chat_request,
    record_chat_response,
    record_llm_request,
    record_rag_retrieval,
    start_timer,
)
from app.llm.client import LLMClient
from app.llm.factory import get_configured_llm_client
from app.rag.factory import get_configured_retriever
from app.rag.models import KnowledgeChunk
from app.rag.prompt_builder import PromptBundle
from app.rag.retriever import Retriever
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService
from app.services.chat_safety import is_prompt_injection_attempt


class MetricsRetriever:
    def __init__(self, retriever: Retriever) -> None:
        self._retriever = retriever

    def retrieve(self, query: str) -> list[KnowledgeChunk]:
        start_time = start_timer()
        try:
            chunks = self._retriever.retrieve(query)
        except Exception:
            record_rag_retrieval(
                outcome="error",
                chunks_count=0,
                duration_seconds=elapsed_seconds(start_time),
            )
            raise

        record_rag_retrieval(
            outcome="success" if chunks else "empty",
            chunks_count=len(chunks),
            duration_seconds=elapsed_seconds(start_time),
        )
        return chunks


class MetricsLLMClient:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def answer(self, prompt: PromptBundle) -> str:
        start_time = start_timer()
        try:
            answer = self._client.answer(prompt)
        except Exception:
            record_llm_request(
                operation="answer",
                outcome="error",
                duration_seconds=elapsed_seconds(start_time),
            )
            raise

        record_llm_request(
            operation="answer",
            outcome="success",
            duration_seconds=elapsed_seconds(start_time),
        )
        return answer

    def stream_answer(self, prompt: PromptBundle) -> Iterator[str]:
        stream_answer = getattr(self._client, "stream_answer", None)
        if not callable(stream_answer):
            return iter(())

        start_time = start_timer()
        try:
            for token in stream_answer(prompt):
                yield token
        except Exception:
            record_llm_request(
                operation="stream",
                outcome="error",
                duration_seconds=elapsed_seconds(start_time),
            )
            raise

        record_llm_request(
            operation="stream",
            outcome="success",
            duration_seconds=elapsed_seconds(start_time),
        )


class MetricsChatService:
    def __init__(self, service: ChatService) -> None:
        self._service = service

    def answer(self, request: ChatRequest) -> ChatResponse:
        try:
            response = self._service.answer(request)
        except Exception:
            record_chat_request(
                mode="json",
                outcome="error",
                policy_intent="none",
            )
            raise

        _record_chat_response_metrics(
            mode="json",
            request=request,
            response=response,
        )
        return response

    async def stream_answer(self, request: ChatRequest) -> AsyncIterator[str]:
        done_payload: dict[str, object] | None = None
        try:
            async for event in self._service.stream_answer(request):
                parsed_payload = _parse_done_event(event)
                if parsed_payload is not None:
                    done_payload = parsed_payload
                yield event
        except Exception:
            record_chat_request(
                mode="stream",
                outcome="error",
                policy_intent="none",
            )
            raise

        if done_payload is not None:
            _record_stream_done_metrics(request=request, payload=done_payload)


def build_metrics_chat_service(settings: Settings) -> MetricsChatService:
    retriever = MetricsRetriever(get_configured_retriever(settings))
    llm_client = get_configured_llm_client(settings)
    instrumented_llm_client = MetricsLLMClient(llm_client) if llm_client is not None else None
    return MetricsChatService(
        ChatService(
            retriever=retriever,
            llm_client=instrumented_llm_client,
        )
    )


def _record_chat_response_metrics(
    *,
    mode: str,
    request: ChatRequest,
    response: ChatResponse,
) -> None:
    outcome, policy_intent = _classify_chat_response(request, response)
    if outcome == "policy":
        record_chat_policy_decision(policy_intent)

    record_chat_request(
        mode=mode,
        outcome=outcome,
        policy_intent=policy_intent,
    )
    record_chat_response(
        mode=mode,
        confidence=response.confidence,
        not_enough_data=response.not_enough_data,
        handoff_suggested=response.handoff_suggested,
    )


def _record_stream_done_metrics(
    *,
    request: ChatRequest,
    payload: dict[str, object],
) -> None:
    response = ChatResponse(
        answer="streamed",
        sources=[],
        confidence=_string_value(payload.get("confidence"), default="low"),
        not_enough_data=payload.get("not_enough_data") is True,
        handoff_suggested=payload.get("handoff_suggested") is True,
        handoff_reason=_optional_string_value(payload.get("handoff_reason")),
        language_unsupported=payload.get("language_unsupported") is True,
        user_requested_human=payload.get("user_requested_human") is True,
    )
    _record_chat_response_metrics(mode="stream", request=request, response=response)


def _classify_chat_response(
    request: ChatRequest,
    response: ChatResponse,
) -> tuple[str, str]:
    if is_prompt_injection_attempt(request.message):
        return "policy", "prompt_injection"
    if response.language_unsupported:
        return "policy", "language_unsupported"
    if response.user_requested_human:
        return "policy", "handoff_request"
    if response.handoff_reason == "private_data":
        return "policy", "private_data"
    if response.handoff_reason == "public_boundary":
        return "policy", "public_boundary"
    if response.not_enough_data:
        return "insufficient_data", response.handoff_reason or "insufficient_data"
    if response.sources:
        return "rag", "none"
    return "scripted", "none"


def _parse_done_event(event: str) -> dict[str, object] | None:
    if not event.startswith("event: done\n"):
        return None
    for line in event.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            payload = json.loads(line.removeprefix("data:").strip())
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None
    return None


def _string_value(value: object, *, default: str) -> str:
    return value if isinstance(value, str) else default


def _optional_string_value(value: object) -> str | None:
    return value if isinstance(value, str) else None
