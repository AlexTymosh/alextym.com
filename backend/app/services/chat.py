import asyncio
import json
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
from app.schemas.chat import ChatHistoryMessage, ChatRequest, ChatResponse, Confidence
from app.services.chat_language import normalize_message as _normalize_message
from app.services.chat_policy import (
    ALEX_TERMS,
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

ALEX_PROFILE_TERMS = (
    "experience",
    "skill",
    "skills",
    "hard skill",
    "hard skills",
    "soft skill",
    "soft skills",
    "strength",
    "strengths",
    "strong side",
    "strong sides",
    "advantage",
    "different",
    "project",
    "projects",
    "resume",
    "cv",
    "education",
    "university",
    "degree",
    "master",
    "master's",
    "masters",
    "mba",
    "academic",
    "honours",
    "scholarship",
    "finance",
    "banking",
    "insurance",
    "work",
    "worked",
    "career",
    "background",
    "intro",
    "profile",
    "portfolio",
    "summary",
    "github",
    "linkedin",
    "contact",
    "availability",
    "available",
    "start",
    "hire",
    "role",
    "stack",
    "python",
    "fastapi",
    "automation",
    "rag",
    "qdrant",
    "prometheus",
    "grafana",
    "observability",
    "metrics",
    "monitoring",
    "backend",
    "api",
    "website",
    "web app",
    "software",
    "program",
    "internal tool",
    "chatbot",
    "collaboration",
    "service",
    "services",
    "integration",
    "right to work",
    "work authorisation",
    "work authorization",
    "share code",
    "uk location",
    "based in the uk",
    "visa",
    "employment eligibility",
    "work permit",
)

SERVICE_REQUEST_TERMS = (
    "build a website",
    "create a website",
    "make a website",
    "need a website",
    "need a program",
    "need a tool",
    "need an internal tool",
    "need software",
    "build a tool",
    "build software",
    "create software",
    "build an app",
    "create an app",
    "automation project",
    "automate my",
    "automate our",
    "api integration",
    "integrate api",
    "internal tool",
    "business automation",
    "rag chatbot",
    "ai assistant",
    f"can {_OWNER_REFERENCE.casefold()} build",
    "can he build",
)

WEAKNESS_REQUEST_TERMS = (
    "weakness",
    "weaknesses",
    "education",
    "university",
    "degree",
    "master",
    "master's",
    "masters",
    "mba",
    "academic",
    "honours",
    "scholarship",
    "finance",
    "banking",
    "insurance",
    "rag",
    "qdrant",
    "prometheus",
    "grafana",
    "observability",
    "metrics",
    "monitoring",
    "weak point",
    "weak points",
    "development area",
    "development areas",
    "areas to improve",
    "limitations",
    f"what should {_OWNER_REFERENCE.casefold()} improve",
    "what should he improve",
)

SECOND_PERSON_TERMS = (
    "you",
    "your",
    "yours",
)

FOLLOW_UP_PRONOUN_TERMS = (
    "he",
    "him",
    "his",
)

FOLLOW_UP_PROFILE_TERMS = (
    "background",
    "career",
    "do",
    "does",
    "experience",
    "profile",
    "project",
    "projects",
    "skill",
    "skills",
    "soft",
    "hard",
    "tell",
    "work",
    "availability",
    "available",
    "start",
    "hire",
    "stack",
    "service",
    "services",
    "website",
    "software",
    "automation",
    "strength",
    "strengths",
    "different",
    "weakness",
    "weaknesses",
)

SHORT_CONTINUATION_PATTERNS = (
    "yes",
    "yes please",
    "sure",
    "please",
    "go ahead",
    "so tell me",
    "tell me",
    "go on",
    "continue",
    "more",
    "more please",
)

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

CONTACT_OR_AVAILABILITY_TERMS = (
    "contact",
    "connect",
    "speak",
    "talk",
    "chat",
    "hire",
    "offer",
    "availability",
    "available",
    "start",
    "start date",
    "new job",
    "right to work",
    "work authorisation",
    "work authorization",
    "share code",
    "uk work",
    "uk location",
    "based in the uk",
    "visa",
    "employment eligibility",
    "work permit",
)

KNOWN_THIRD_PARTY_SUBJECTS = ("elon musk",)


@dataclass(frozen=True)
class QuestionResolution:
    is_alex_specific: bool
    retrieval_query: str
    conversational_context: str
    is_out_of_scope_subject: bool = False


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

    async def stream_answer(self, request: ChatRequest) -> AsyncIterator[str]:
        request_id = str(uuid.uuid4())
        yield self._sse_event("meta", {"request_id": request_id, "status": "started"})

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

        resolution = self._resolve_question(request)
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
            confidence=_confidence_from_chunks(chunks, request.message),
            handoff_suggested=_should_offer_handoff_after_answer(request.message),
            handoff_reason=_handoff_reason_after_answer(request.message),
        )

    async def _stream_rag_answer(
        self,
        *,
        request_id: str,
        context: RagAnswerContext,
    ) -> AsyncIterator[str]:
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
                        yield self._sse_event(
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
                        yield self._sse_event("token", {"text": safe_output})
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
                yield self._sse_event(
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
            yield self._sse_event("token", {"text": pending_output})

        response = self._rag_response(answer=streamed_answer, context=context)
        yield self._sources_event(response)
        yield self._done_event(request_id=request_id, response=response)

    async def _stream_response_payload(
        self,
        *,
        request_id: str,
        response: ChatResponse,
    ) -> AsyncIterator[str]:
        for token in self._tokenize(response.answer):
            yield self._sse_event("token", {"text": token})
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

    def _sources_event(self, response: ChatResponse) -> str:
        return self._sse_event(
            "sources",
            {"sources": [source.model_dump() for source in response.sources]},
        )

    def _done_event(self, *, request_id: str, response: ChatResponse) -> str:
        return self._sse_event(
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
            is_weakness_request=_is_weakness_request,
        )

    @staticmethod
    def _prompt_injection_response() -> ChatResponse:
        return prompt_injection_response()

    @staticmethod
    def _handoff_request_response() -> ChatResponse:
        return handoff_request_response()

    @staticmethod
    def _is_alex_specific_question(message: str) -> bool:
        normalized_message = _normalize_message(message)
        if any(term in normalized_message for term in ALEX_TERMS):
            return True
        if _looks_like_profile_topic(normalized_message):
            return True
        return bool(
            any(term in normalized_message for term in SECOND_PERSON_TERMS)
            and any(term in normalized_message for term in ALEX_PROFILE_TERMS)
        )

    def _resolve_question(self, request: ChatRequest) -> QuestionResolution:
        conversational_context = _format_conversation_context(request.history)
        normalized_message = _normalize_message(request.message)

        if _is_direct_third_party_subject(normalized_message):
            return QuestionResolution(
                is_alex_specific=False,
                retrieval_query=request.message,
                conversational_context=conversational_context,
                is_out_of_scope_subject=True,
            )

        if self._is_alex_specific_question(request.message):
            return QuestionResolution(
                is_alex_specific=True,
                retrieval_query=_rewrite_alex_retrieval_query(request.message),
                conversational_context=conversational_context,
            )

        if _is_service_request(request.message):
            return QuestionResolution(
                is_alex_specific=True,
                retrieval_query=_services_retrieval_query(),
                conversational_context=conversational_context,
            )

        subject = _last_explicit_user_subject(request.history)
        has_alex_context = _history_has_alex_assistant_context(request.history)

        classifier_resolution = self._try_llm_intent_resolution(
            request=request,
            conversational_context=conversational_context,
        )
        if classifier_resolution is not None:
            return classifier_resolution

        if _is_follow_up_profile_question(normalized_message):
            if subject == "third_party":
                return QuestionResolution(
                    is_alex_specific=False,
                    retrieval_query=request.message,
                    conversational_context=conversational_context,
                    is_out_of_scope_subject=True,
                )
            if subject == "alex" or has_alex_context:
                return QuestionResolution(
                    is_alex_specific=True,
                    retrieval_query=_rewrite_alex_retrieval_query(request.message),
                    conversational_context=conversational_context,
                )

        if has_alex_context and _looks_like_short_continuation(normalized_message):
            return QuestionResolution(
                is_alex_specific=True,
                retrieval_query=(
                    f"Continue answering about {_OWNER_POSSESSIVE} professional "
                    f"profile based on the previous {_OWNER_REFERENCE}-related question."
                ),
                conversational_context=conversational_context,
            )

        if has_alex_context and _looks_like_short_profile_follow_up(normalized_message):
            return QuestionResolution(
                is_alex_specific=True,
                retrieval_query=_rewrite_alex_retrieval_query(request.message),
                conversational_context=conversational_context,
            )

        return QuestionResolution(
            is_alex_specific=False,
            retrieval_query=request.message,
            conversational_context=conversational_context,
        )

    def _try_llm_intent_resolution(
        self,
        *,
        request: ChatRequest,
        conversational_context: str,
    ) -> QuestionResolution | None:
        if self._llm_client is None:
            return None
        if not _should_use_intent_classifier(request):
            return None

        prompt = PromptBundle(
            system=(
                f"Classify whether the user is asking about {_OWNER_POSSESSIVE} public "
                "professional profile or software services. Return only compact "
                "JSON with keys: intent, rewritten_query, confidence, reason."
            ),
            context=conversational_context or "No conversation context.",
            question=request.message,
        )
        try:
            raw_answer = self._llm_client.answer(prompt)
        except (ProviderConfigurationError, ProviderRequestError):
            return None

        try:
            payload = json.loads(raw_answer)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None
        supported_intents = {"alex_profile_question", "alex_services_question"}
        if payload.get("intent") not in supported_intents:
            return None

        rewritten_query = payload.get("rewritten_query")
        if not isinstance(rewritten_query, str) or not rewritten_query.strip():
            return None

        return QuestionResolution(
            is_alex_specific=True,
            retrieval_query=rewritten_query.strip(),
            conversational_context=conversational_context,
        )

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

    @staticmethod
    def _sse_event(event: str, data: dict[str, Any]) -> str:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return f"event: {event}\ndata: {payload}\n\n"


def _llm_token_stream(
    client: LLMClient,
    prompt: PromptBundle,
) -> Iterator[str] | None:
    stream_answer = getattr(client, "stream_answer", None)
    if not callable(stream_answer):
        return None
    return stream_answer(prompt)


def _confidence_from_chunks(chunks: list[KnowledgeChunk], query: str) -> Confidence:
    if not chunks:
        return "low"

    scores = sorted(
        (score for chunk in chunks if (score := _retrieval_score(chunk)) is not None),
        reverse=True,
    )
    top_score = scores[0] if scores else None
    score_gap = scores[0] - scores[1] if len(scores) > 1 else 0.0
    source_rank = max(_source_confidence_rank(chunk) for chunk in chunks)
    answer_fact_count = sum(_answer_fact_count(chunk) for chunk in chunks[:3])
    exact_match = _has_exact_metadata_match(query, chunks[:3])

    if top_score is None:
        if exact_match and source_rank >= 2:
            return "high"
        if answer_fact_count >= 2 or source_rank >= 2:
            return "medium"
        return "low"

    if top_score >= 0.78 and (score_gap >= 0.05 or exact_match):
        return "high"
    if top_score >= 0.72 and answer_fact_count >= 2 and source_rank >= 2:
        return "high"
    if top_score >= 0.55 or exact_match or answer_fact_count >= 2:
        return "medium"
    return "low"


def _retrieval_score(chunk: KnowledgeChunk) -> float | None:
    value = chunk.metadata.extra.get("retrieval_score")
    return float(value) if isinstance(value, (int, float)) else None


def _source_confidence_rank(chunk: KnowledgeChunk) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(
        chunk.metadata.source_confidence,
        2,
    )


def _answer_fact_count(chunk: KnowledgeChunk) -> int:
    value = chunk.metadata.extra.get("answer_facts")
    if not isinstance(value, list):
        return 0
    return sum(1 for item in value if isinstance(item, str) and item.strip())


def _has_exact_metadata_match(query: str, chunks: list[KnowledgeChunk]) -> bool:
    query_terms = _confidence_terms(query)
    if not query_terms:
        return False

    for chunk in chunks:
        metadata_terms = _confidence_terms(
            " ".join(
                [
                    chunk.metadata.section,
                    chunk.metadata.topic,
                    " ".join(chunk.metadata.tags),
                ]
            )
        )
        if query_terms.intersection(metadata_terms):
            return True
    return False


def _confidence_terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9]+", value.casefold()) if len(term) > 3}


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


def _format_conversation_context(history: list[ChatHistoryMessage]) -> str:
    lines = []
    for item in history:
        content = " ".join(item.content.split())
        if len(content) > 500:
            content = content[:497].rstrip() + "..."
        lines.append(f"{item.role}: {content}")
    return "\n".join(lines)


def _is_weakness_request(
    message: str,
    history: list[ChatHistoryMessage],
) -> bool:
    normalized_message = _normalize_message(message)
    if _looks_like_profile_topic(normalized_message):
        return False
    if not any(term in normalized_message for term in WEAKNESS_REQUEST_TERMS):
        return False
    if _is_direct_third_party_subject(normalized_message):
        return False
    if any(term in normalized_message for term in ALEX_TERMS):
        return True
    if any(term in normalized_message for term in SECOND_PERSON_TERMS):
        return True
    if any(term in normalized_message for term in FOLLOW_UP_PRONOUN_TERMS):
        return _history_has_alex_assistant_context(history)
    return False


def _is_service_request(message: str) -> bool:
    normalized_message = _normalize_message(message)
    return any(term in normalized_message for term in SERVICE_REQUEST_TERMS)


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


def _is_contact_or_availability_question(message: str) -> bool:
    normalized_message = _normalize_message(message)
    return any(term in normalized_message for term in CONTACT_OR_AVAILABILITY_TERMS)


def _should_offer_handoff_after_answer(message: str) -> bool:
    return _is_contact_or_availability_question(message) or _is_service_request(message)


def _handoff_reason_after_answer(message: str) -> str | None:
    if _is_service_request(message):
        return "service_enquiry"
    if _is_contact_or_availability_question(message):
        return "user_requested_human"
    return None


def _answer_mentions_handoff(answer: str) -> bool:
    normalized_answer = _normalize_message(answer)
    return (
        "connect" in normalized_answer
        or "connection" in normalized_answer
        or "handoff" in normalized_answer
    )


def _is_direct_third_party_subject(normalized_message: str) -> bool:
    if any(term in normalized_message for term in ALEX_TERMS):
        return False
    return any(subject in normalized_message for subject in KNOWN_THIRD_PARTY_SUBJECTS)


def _is_follow_up_profile_question(normalized_message: str) -> bool:
    tokens = set(normalized_message.split())
    if not tokens.intersection(FOLLOW_UP_PRONOUN_TERMS):
        return False
    return bool(tokens.intersection(FOLLOW_UP_PROFILE_TERMS)) or bool(
        _looks_like_profile_topic(normalized_message)
    )


def _looks_like_short_profile_follow_up(normalized_message: str) -> bool:
    if not normalized_message:
        return False
    if len(normalized_message.split()) > 8:
        return False
    return any(term in normalized_message for term in FOLLOW_UP_PROFILE_TERMS) or bool(
        _looks_like_profile_topic(normalized_message)
    )


def _looks_like_short_continuation(normalized_message: str) -> bool:
    return normalized_message in SHORT_CONTINUATION_PATTERNS


def _looks_like_profile_topic(normalized_message: str) -> bool:
    education_terms = (
        "academic",
        "banking",
        "degree",
        "education",
        "finance",
        "honours",
        "insurance",
        "master",
        "master's",
        "masters",
        "mba",
        "scholarship",
        "university",
    )
    rag_project_terms = (
        "grafana",
        "metrics",
        "monitoring",
        "observability",
        "prometheus",
        "qdrant",
        "rag",
        "retrieval augmented",
        "vector search",
    )
    return any(term in normalized_message for term in education_terms) or any(
        term in normalized_message for term in rag_project_terms
    )


def _should_use_intent_classifier(request: ChatRequest) -> bool:
    normalized_message = _normalize_message(request.message)
    if any(term in normalized_message for term in ALEX_TERMS):
        return False
    if not any(term in normalized_message for term in FOLLOW_UP_PRONOUN_TERMS):
        return False
    return _history_has_alex_assistant_context(request.history)


def _last_explicit_user_subject(history: list[ChatHistoryMessage]) -> str | None:
    for item in reversed(history):
        if item.role != "user":
            continue
        normalized_content = _normalize_message(item.content)
        if any(subject in normalized_content for subject in KNOWN_THIRD_PARTY_SUBJECTS):
            return "third_party"
        if any(term in normalized_content for term in ALEX_TERMS):
            return "alex"
    return None


def _history_has_alex_assistant_context(history: list[ChatHistoryMessage]) -> bool:
    owner_markers = _owner_context_markers()
    for item in reversed(history):
        if item.role != "assistant":
            continue
        normalized_content = _normalize_message(item.content)
        if any(marker in normalized_content for marker in owner_markers):
            return True
    return False


def _owner_context_markers() -> tuple[str, ...]:
    owner_markers = set(ALEX_TERMS)
    owner_markers.add(_normalize_message(_PROJECT_CONFIG.assistant.display_name))
    owner_markers.add(_normalize_message(UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER))
    owner_markers.add(_normalize_message(UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER))

    for owner_term in ALEX_TERMS:
        owner_markers.update(
            {
                f"ask about {owner_term}",
                f"{owner_term} builds",
                f"{owner_term} focuses",
                f"{owner_term} has",
                f"{owner_term} holds",
                f"{owner_term} worked",
                f"{owner_term} public",
                f"{owner_term} profile",
            }
        )

    return tuple(marker for marker in owner_markers if marker)


def _services_retrieval_query() -> str:
    return (
        f"Tell me about {_OWNER_POSSESSIVE} software services, automation projects, "
        "websites, API integrations, internal tools, RAG chatbots, and "
        "collaboration options."
    )


def _rewrite_alex_retrieval_query(message: str) -> str:
    normalized_message = _normalize_message(message)
    if normalized_message == "tell me about him" or any(
        normalized_message == f"tell me about {owner_term}" for owner_term in ALEX_TERMS
    ):
        return (
            f"Tell me about {_OWNER_POSSESSIVE} professional background, "
            "experience, skills, and projects."
        )
    if normalized_message == "what does he do":
        return f"What does {_OWNER_REFERENCE} do professionally?"
    if any(
        term in normalized_message
        for term in (
            "academic",
            "banking",
            "degree",
            "education",
            "finance",
            "honours",
            "insurance",
            "master",
            "master's",
            "masters",
            "mba",
            "scholarship",
            "university",
        )
    ):
        return (
            f"Tell me about {_OWNER_POSSESSIVE} education, Master's Degree in Finance, "
            "Banking and Insurance, university, honours, academic "
            "scholarship, and analytical background."
        )
    if any(
        term in normalized_message
        for term in (
            "grafana",
            "metrics",
            "monitoring",
            "observability",
            "prometheus",
            "qdrant",
            "rag",
            "retrieval augmented",
            "vector search",
        )
    ):
        return (
            f"Tell me about {_OWNER_POSSESSIVE} AI portfolio website, RAG architecture, "
            "retrieval pipeline, Qdrant vector search, Prometheus, Grafana, "
            "observability, evals, and production-oriented safeguards."
        )
    if "work" in normalized_message and "experience" in normalized_message:
        return f"Tell me about {_OWNER_POSSESSIVE} work experience."
    if any(
        term in normalized_message
        for term in (
            "mba",
            "university",
            "degree",
            "master",
            "master's",
            "education",
            "finance",
            "banking",
            "insurance",
        )
    ):
        return (
            f"Tell me about {_OWNER_POSSESSIVE} education, university degree, finance "
            "background, and academic achievements."
        )
    if any(term in normalized_message for term in ("rag", "qdrant", "embedding")):
        return (
            f"Tell me about {_OWNER_POSSESSIVE} RAG portfolio website, architecture, "
            "retrieval system, safeguards, evaluations, and AI assistant."
        )
    if any(
        term in normalized_message for term in ("prometheus", "grafana", "observability", "metrics")
    ):
        return (
            f"Tell me about {_OWNER_POSSESSIVE} observability work with Prometheus, "
            "Grafana, metrics, dashboards, and monitoring."
        )
    if "soft" in normalized_message and "skill" in normalized_message:
        return (
            f"Tell me about {_OWNER_POSSESSIVE} soft skills, working style, collaboration, "
            "communication, and problem-solving."
        )
    if "hard" in normalized_message and "skill" in normalized_message:
        return (
            f"Tell me about {_OWNER_POSSESSIVE} hard skills, technical stack, tools, "
            "and software engineering capabilities."
        )
    if any(term in normalized_message for term in ("service", "website", "software")):
        return _services_retrieval_query()
    if "strength" in normalized_message or "different" in normalized_message:
        return (
            f"Tell me about {_OWNER_POSSESSIVE} professional strengths, working style, "
            "automation-first thinking, and collaboration approach."
        )
    if "your" in normalized_message and "project" in normalized_message:
        return f"Tell me about {_OWNER_POSSESSIVE} professional projects and software work."
    if _is_follow_up_profile_question(normalized_message):
        return (
            f"Tell me about {_OWNER_POSSESSIVE} professional background, "
            "experience, skills, and projects."
        )
    return message
