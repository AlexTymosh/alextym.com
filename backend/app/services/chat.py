import asyncio
import re
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Any

from app.core.project_config import get_project_config
from app.llm.client import LLMClient, ProviderConfigurationError, ProviderRequestError
from app.llm.factory import get_configured_llm_client
from app.rag.factory import get_configured_retriever
from app.rag.models import KnowledgeChunk
from app.rag.prompt_builder import PromptBuilder, PromptBundle
from app.rag.retriever import Retriever
from app.schemas.chat import ChatRequest, ChatResponse, Confidence
from app.schemas.sse import ServerSentEvent
from app.services.chat_confidence import confidence_from_chunks
from app.services.chat_intent_resolution import (
    handoff_reason_after_answer,
    is_weakness_request,
    resolve_question,
    should_offer_handoff_after_answer,
)
from app.services.chat_language import normalize_message as _normalize_message
from app.services.chat_policy import (
    ASSISTANT_INTRO_ANSWER,
    GREETING_ANSWER,
    HANDOFF_PROMPT_TITLE,
    HANDOFF_REQUEST_ANSWER,
    HELP_ANSWER,
    INSUFFICIENT_DATA_ANSWER,
    OUT_OF_SCOPE_ANSWER,
    PRIVATE_DATA_ANSWER,
    PROMPT_INJECTION_ANSWER,
    PUBLIC_BOUNDARY_WEAKNESSES_ANSWER,
    SOCIAL_ACKNOWLEDGEMENT_ANSWER,
    UNSUPPORTED_NON_ENGLISH_ANSWER,
    UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER,
    UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER,
    ChatPolicyResult,
    apply_pre_rag_policy,
    handoff_request_response,
    prompt_injection_response,
)
from app.services.chat_safety import is_unsafe_chat_output

__all__ = [
    "ASSISTANT_INTRO_ANSWER",
    "ChatService",
    "GREETING_ANSWER",
    "HANDOFF_REQUEST_ANSWER",
    "HELP_ANSWER",
    "INSUFFICIENT_DATA_ANSWER",
    "OUT_OF_SCOPE_ANSWER",
    "PRIVATE_DATA_ANSWER",
    "PROMPT_INJECTION_ANSWER",
    "PUBLIC_BOUNDARY_WEAKNESSES_ANSWER",
    "SOCIAL_ACKNOWLEDGEMENT_ANSWER",
    "UNSUPPORTED_NON_ENGLISH_ANSWER",
    "UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER",
    "UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER",
]

_PROJECT_CONFIG = get_project_config()
_OWNER_REFERENCE = _PROJECT_CONFIG.assistant.owner_reference
_OWNER_POSSESSIVE = _PROJECT_CONFIG.owner.possessive_name

STREAM_GUARD_BUFFER_CHARS = 160

HANDOFF_REQUEST_PATTERNS = (
    "connect",
    "connect me",
    "hire him",
    "i'd like to hire him",
    "i would like to hire him",
    "offer him",
    "best offer",
    "share code",
    "right to work share code",
    "uk share code",
    f"connect me with {_OWNER_REFERENCE.casefold()}",
    f"connect me to {_OWNER_REFERENCE.casefold()}",
    f"speak with {_OWNER_REFERENCE.casefold()}",
    f"talk to {_OWNER_REFERENCE.casefold()}",
    f"talk with {_OWNER_REFERENCE.casefold()}",
    f"chat with {_OWNER_REFERENCE.casefold()}",
    f"i want to speak with {_OWNER_REFERENCE.casefold()}",
    f"i would like to speak with {_OWNER_REFERENCE.casefold()}",
    f"i'd like to speak with {_OWNER_REFERENCE.casefold()}",
    f"i confirm i'd like to speak with {_OWNER_REFERENCE.casefold()}",
    f"i confirm i would like to speak with {_OWNER_REFERENCE.casefold()}",
    f"give me {_OWNER_REFERENCE.casefold()}",
    f"get me {_OWNER_REFERENCE.casefold()}",
    f"hire {_OWNER_REFERENCE.casefold()}",
    f"i want to hire {_OWNER_REFERENCE.casefold()}",
    f"offer {_OWNER_REFERENCE.casefold()}",
    "\u0441\u043e\u0435\u0434\u0438\u043d\u0438 \u043c\u0435\u043d\u044f",
    "\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u0442\u0435 \u043c\u0435\u043d\u044f",
    (
        "\u0445\u043e\u0447\u0443 "
        "\u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u044c "
        "\u0441 \u0430\u043b\u0435\u043a\u0441\u043e\u043c"
    ),
    (
        "\u0445\u043e\u0447\u0443 "
        "\u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u0438 "
        "\u0437 \u0430\u043b\u0435\u043a\u0441\u043e\u043c"
    ),
    (
        "\u0445\u043e\u0447\u0443 "
        "\u0437\u0432'\u044f\u0437\u0430\u0442\u0438\u0441\u044f "
        "\u0437 \u0430\u043b\u0435\u043a\u0441\u043e\u043c"
    ),
    (
        "\u0445\u043e\u0447\u0443 "
        "\u0441\u0432\u044f\u0437\u0430\u0442\u044c\u0441\u044f "
        "\u0441 \u0430\u043b\u0435\u043a\u0441\u043e\u043c"
    ),
    (
        "\u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u044c "
        "\u0441 \u0430\u043b\u0435\u043a\u0441\u043e\u043c"
    ),
)

HANDOFF_CONFIRMATION_PATTERNS = (
    "yes",
    "yeah",
    "yep",
    "sure",
    "ok",
    "okay",
    "confirm",
    "i confirm",
    "yes please",
    "please do",
    "\u0434\u0430",
    "\u0442\u0430\u043a",
    "\u043e\u043a",
    "\u043e\u043a\u0435\u0439",
    "\u0434\u043e\u0431\u0440\u0435",
    "\u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430",
    "\u0431\u0443\u0434\u044c \u043b\u0430\u0441\u043a\u0430",
)


@dataclass(frozen=True)
class RagAnswerContext:
    prompt: PromptBundle
    chunks: list[KnowledgeChunk]
    confidence: Confidence
    handoff_suggested: bool
    handoff_reason: str | None


class ChatService:
    def __init__(
        self,
        retriever: Retriever | None = None,
        llm_client: LLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._retriever = retriever or get_configured_retriever()
        self._llm_client = (
            llm_client
            if llm_client is not None
            else (get_configured_llm_client() if retriever is None else None)
        )
        self._prompt_builder = prompt_builder or PromptBuilder()

    def answer(self, request: ChatRequest) -> ChatResponse:
        prepared_answer = self._prepare_answer(request)
        if isinstance(prepared_answer, ChatPolicyResult):
            return prepared_answer.response

        answer = self._answer_from_prompt(
            prepared_answer.prompt,
            prepared_answer.chunks,
        )
        if is_unsafe_chat_output(answer):
            return self._prompt_injection_response()
        return self._rag_response(answer=answer, context=prepared_answer)

    async def stream_answer(self, request: ChatRequest) -> AsyncIterator[ServerSentEvent]:
        request_id = str(uuid.uuid4())
        yield ServerSentEvent("meta", {"request_id": request_id, "status": "started"})

        prepared_answer = self._prepare_answer(request)
        if isinstance(prepared_answer, ChatPolicyResult):
            async for event in self._stream_response_payload(
                request_id=request_id,
                response=prepared_answer.response,
            ):
                yield event
            return

        async for event in self._stream_rag_answer(
            request_id=request_id,
            context=prepared_answer,
        ):
            yield event

    def _prepare_answer(
        self,
        request: ChatRequest,
    ) -> ChatPolicyResult | RagAnswerContext:
        policy_result = self._apply_pre_rag_policy(request)
        if policy_result is not None:
            return policy_result

        resolution = resolve_question(request, llm_client=self._llm_client)
        if resolution.is_out_of_scope_subject or not resolution.is_alex_specific:
            return ChatPolicyResult(
                intent="out_of_scope",
                response=self._out_of_scope_response(),
            )

        try:
            chunks = self._retriever.retrieve(resolution.retrieval_query)
        except (ProviderConfigurationError, ProviderRequestError):
            return ChatPolicyResult(
                intent="insufficient_data",
                response=self._insufficient_data_response(),
            )

        if not chunks:
            return ChatPolicyResult(
                intent="insufficient_data",
                response=self._insufficient_data_response(),
            )

        prompt = self._prompt_builder.build(
            question=request.message,
            chunks=chunks,
            conversational_context=resolution.conversational_context,
        )
        return RagAnswerContext(
            prompt=prompt,
            chunks=chunks,
            confidence=confidence_from_chunks(chunks, request.message),
            handoff_suggested=should_offer_handoff_after_answer(request.message),
            handoff_reason=handoff_reason_after_answer(request.message),
        )

    async def _stream_rag_answer(
        self,
        *,
        request_id: str,
        context: RagAnswerContext,
    ) -> AsyncIterator[ServerSentEvent]:
        if self._llm_client is None:
            response = self._rag_response(
                answer=self._extractive_answer(context.chunks, context.prompt.context),
                context=context,
            )
            async for event in self._stream_response_payload(
                request_id=request_id,
                response=response,
            ):
                yield event
            return

        streamed_answer = ""
        pending_output = ""
        emitted_any_token = False
        try:
            token_stream = _llm_token_stream(self._llm_client, context.prompt)
        except (ProviderConfigurationError, ProviderRequestError):
            token_stream = None

        if token_stream is None:
            answer = self._answer_from_prompt(context.prompt, context.chunks)
            response = (
                self._prompt_injection_response()
                if is_unsafe_chat_output(answer)
                else self._rag_response(answer=answer, context=context)
            )
            async for event in self._stream_response_payload(
                request_id=request_id,
                response=response,
            ):
                yield event
            return

        try:
            for token in token_stream:
                if not token:
                    continue
                streamed_answer += token
                pending_output += token

                if is_unsafe_chat_output(streamed_answer):
                    response = self._prompt_injection_response()
                    if emitted_any_token:
                        yield ServerSentEvent(
                            "error",
                            {"message": "Unsafe generated output was blocked."},
                        )
                        yield self._done_event(
                            request_id=request_id,
                            response=response,
                        )
                    else:
                        async for event in self._stream_response_payload(
                            request_id=request_id,
                            response=response,
                        ):
                            yield event
                    return

                if len(pending_output) > STREAM_GUARD_BUFFER_CHARS:
                    safe_output = pending_output[:-STREAM_GUARD_BUFFER_CHARS]
                    pending_output = pending_output[-STREAM_GUARD_BUFFER_CHARS:]
                    if safe_output:
                        emitted_any_token = True
                        yield ServerSentEvent("token", {"text": safe_output})
                        await asyncio.sleep(0)
        except (ProviderConfigurationError, ProviderRequestError):
            response = self._rag_response(
                answer=self._extractive_answer(context.chunks, context.prompt.context),
                context=context,
            )
            async for event in self._stream_response_payload(
                request_id=request_id,
                response=response,
            ):
                yield event
            return

        if not streamed_answer.strip():
            response = self._rag_response(
                answer=self._extractive_answer(context.chunks, context.prompt.context),
                context=context,
            )
            async for event in self._stream_response_payload(
                request_id=request_id,
                response=response,
            ):
                yield event
            return

        if is_unsafe_chat_output(streamed_answer):
            response = self._prompt_injection_response()
            if emitted_any_token:
                yield ServerSentEvent(
                    "error",
                    {"message": "Unsafe generated output was blocked."},
                )
                yield self._done_event(
                    request_id=request_id,
                    response=response,
                )
            else:
                async for event in self._stream_response_payload(
                    request_id=request_id,
                    response=response,
                ):
                    yield event
            return

        if pending_output:
            yield ServerSentEvent("token", {"text": pending_output})

        response = self._rag_response(answer=streamed_answer, context=context)
        yield self._sources_event(response)
        yield self._done_event(request_id=request_id, response=response)

    async def _stream_response_payload(
        self,
        *,
        request_id: str,
        response: ChatResponse,
    ) -> AsyncIterator[ServerSentEvent]:
        for token in self._tokenize(response.answer):
            yield ServerSentEvent("token", {"text": token})
            await asyncio.sleep(0)
        yield self._sources_event(response)
        yield self._done_event(request_id=request_id, response=response)

    def _rag_response(
        self,
        *,
        answer: str,
        context: RagAnswerContext,
    ) -> ChatResponse:
        if context.handoff_suggested and not _answer_mentions_handoff(answer):
            answer = answer.rstrip() + "\n\n" + HANDOFF_PROMPT_TITLE

        return ChatResponse(
            answer=answer,
            sources=[
                {
                    "title": chunk.metadata.source,
                    "section": chunk.metadata.section,
                    "confidence": chunk.metadata.source_confidence,
                }
                for chunk in context.chunks
            ],
            confidence=context.confidence,
            not_enough_data=False,
            handoff_suggested=context.handoff_suggested,
            handoff_reason=context.handoff_reason,
            language_unsupported=False,
            user_requested_human=False,
        )

    def _sources_event(self, response: ChatResponse) -> ServerSentEvent:
        return ServerSentEvent(
            "sources",
            {"sources": [source.model_dump() for source in response.sources]},
        )

    def _done_event(self, *, request_id: str, response: ChatResponse) -> ServerSentEvent:
        return ServerSentEvent(
            "done",
            {
                "request_id": request_id,
                "confidence": response.confidence,
                "not_enough_data": response.not_enough_data,
                "handoff_suggested": response.handoff_suggested,
                "handoff_reason": response.handoff_reason,
                "language_unsupported": response.language_unsupported,
                "user_requested_human": response.user_requested_human,
            },
        )

    def _apply_pre_rag_policy(self, request: ChatRequest) -> ChatPolicyResult | None:
        return apply_pre_rag_policy(
            request,
            is_handoff_request=_is_handoff_request,
            is_handoff_confirmation_after_prompt=_is_handoff_confirmation_after_prompt,
            is_weakness_request=is_weakness_request,
        )

    @staticmethod
    def _prompt_injection_response() -> ChatResponse:
        return prompt_injection_response()

    @staticmethod
    def _handoff_request_response() -> ChatResponse:
        return handoff_request_response()

    @staticmethod
    def _extractive_answer(chunks: list[KnowledgeChunk], context: str) -> str:
        if not context.strip():
            return INSUFFICIENT_DATA_ANSWER

        excerpts = [_first_sentence(chunk.content) for chunk in chunks[:2]]
        excerpts = [excerpt for excerpt in excerpts if excerpt]
        if not excerpts:
            return INSUFFICIENT_DATA_ANSWER

        if len(excerpts) == 1:
            return f"According to {_OWNER_POSSESSIVE} public knowledge base, {excerpts[0]}"

        return f"According to {_OWNER_POSSESSIVE} public knowledge base, " + " ".join(
            f"{index}. {excerpt}" for index, excerpt in enumerate(excerpts, start=1)
        )

    def _answer_from_prompt(self, prompt: Any, chunks: list[KnowledgeChunk]) -> str:
        if self._llm_client is None:
            return self._extractive_answer(chunks, prompt.context)

        try:
            return self._llm_client.answer(prompt)
        except (ProviderConfigurationError, ProviderRequestError):
            return self._extractive_answer(chunks, prompt.context)

    @staticmethod
    def _insufficient_data_response() -> ChatResponse:
        return ChatResponse(
            answer=INSUFFICIENT_DATA_ANSWER,
            sources=[],
            confidence="low",
            not_enough_data=True,
            handoff_suggested=True,
            handoff_reason="insufficient_data",
        )

    @staticmethod
    def _out_of_scope_response() -> ChatResponse:
        return ChatResponse(
            answer=OUT_OF_SCOPE_ANSWER,
            sources=[],
            confidence="medium",
            not_enough_data=False,
            handoff_suggested=False,
        )

    @staticmethod
    def _tokenize(answer: str) -> list[str]:
        words = answer.split(" ")
        tokens = [words[0]] if words else []
        tokens.extend(f" {word}" for word in words[1:])
        return tokens


def _llm_token_stream(
    client: LLMClient,
    prompt: PromptBundle,
) -> Iterator[str] | None:
    stream_answer = getattr(client, "stream_answer", None)
    if not callable(stream_answer):
        return None
    return stream_answer(prompt)


def _first_sentence(text: str, max_length: int = 220) -> str:
    normalized_text = " ".join(text.split())
    if not normalized_text:
        return ""

    sentence_end_candidates = [". ", "! ", "? "]
    sentence_end_indexes = [
        normalized_text.find(candidate) + 1
        for candidate in sentence_end_candidates
        if normalized_text.find(candidate) != -1
    ]
    end_index = min(sentence_end_indexes) if sentence_end_indexes else len(normalized_text)
    sentence = normalized_text[:end_index].strip()

    if len(sentence) <= max_length:
        return sentence

    return sentence[: max_length - 1].rstrip() + "..."


def _is_handoff_request(message: str) -> bool:
    normalized_message = _normalize_message(message)
    normalized_message = re.sub(r"\bcon+ect\b", "connect", normalized_message)
    return any(pattern in normalized_message for pattern in HANDOFF_REQUEST_PATTERNS)


def _is_handoff_confirmation_after_prompt(request: ChatRequest) -> bool:
    normalized_message = _normalize_message(request.message)
    if normalized_message not in HANDOFF_CONFIRMATION_PATTERNS:
        return False

    for item in reversed(request.history):
        if item.role != "assistant":
            continue
        normalized_content = _normalize_message(item.content)
        language_fallback_prompts = {
            _normalize_message(UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER),
            _normalize_message(UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER),
        }
        return (
            "connect" in normalized_content
            or "connection" in normalized_content
            or "handoff" in normalized_content
            or normalized_content in language_fallback_prompts
        )

    return False


def _answer_mentions_handoff(answer: str) -> bool:
    normalized_answer = _normalize_message(answer)
    return (
        "connect" in normalized_answer
        or "connection" in normalized_answer
        or "handoff" in normalized_answer
    )
