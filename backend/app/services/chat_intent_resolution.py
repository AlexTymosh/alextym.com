import re
from dataclasses import dataclass
from typing import Literal

from app.core.project_config import get_project_config
from app.llm.client import ProviderConfigurationError, ProviderRequestError
from app.rag.query_router import route_query
from app.schemas.chat import ChatHistoryMessage, ChatRequest
from app.services.chat_copy import (
    UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER,
    UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER,
)
from app.services.chat_intent_terms import (
    ALEX_PROFILE_TERMS,
    ALEX_TERMS,
    CONTACT_OR_AVAILABILITY_TERMS,
    EDUCATION_PROFILE_TERMS,
    FOLLOW_UP_PROFILE_TERMS,
    FOLLOW_UP_PRONOUN_TERMS,
    KNOWN_THIRD_PARTY_SUBJECTS,
    RAG_PROJECT_TERMS,
    SECOND_PERSON_TERMS,
    SERVICE_REQUEST_TERMS,
    SHORT_CONTINUATION_PATTERNS,
)
from app.services.chat_language import normalize_message
from app.services.question_contextualizer import QuestionContextualizer

_PROJECT_CONFIG = get_project_config()
_OWNER_REFERENCE = _PROJECT_CONFIG.assistant.owner_reference
_OWNER_POSSESSIVE = _PROJECT_CONFIG.owner.possessive_name
_OWNER_PRONOUN_PATTERN = re.compile(r"\b(his|him|he|yours|your|you)\b", re.IGNORECASE)


QuestionIntent = Literal[
    "alex_profile_question",
    "alex_services_question",
    "third_party_question",
    "out_of_scope_question",
    "clarification_required",
]
QuestionResolutionMethod = Literal["rules", "llm", "fallback"]

_RAG_QUESTION_INTENTS = {
    "alex_profile_question",
    "alex_services_question",
}


@dataclass(frozen=True)
class QuestionResolution:
    intent: QuestionIntent
    original_question: str
    standalone_question: str | None
    conversational_context: str
    resolution_method: QuestionResolutionMethod

    def __post_init__(self) -> None:
        if self.requires_retrieval and not self.standalone_question:
            raise ValueError("A retrieval resolution requires a standalone question.")

    @property
    def requires_retrieval(self) -> bool:
        return self.intent in _RAG_QUESTION_INTENTS

    @property
    def requires_clarification(self) -> bool:
        return self.intent == "clarification_required"


def resolve_question(
    request: ChatRequest,
    *,
    question_contextualizer: QuestionContextualizer | None,
) -> QuestionResolution:
    conversational_context = format_conversation_context(request.history)
    normalized_message = normalize_message(request.message)

    if is_direct_third_party_subject(normalized_message):
        return QuestionResolution(
            intent="third_party_question",
            original_question=request.message,
            standalone_question=None,
            conversational_context=conversational_context,
            resolution_method="rules",
        )

    if is_alex_specific_question(request.message):
        return QuestionResolution(
            intent="alex_profile_question",
            original_question=request.message,
            standalone_question=_resolve_alex_subject(request.message),
            conversational_context=conversational_context,
            resolution_method="rules",
        )

    if is_service_request(request.message):
        return QuestionResolution(
            intent="alex_services_question",
            original_question=request.message,
            standalone_question=_services_retrieval_query(),
            conversational_context=conversational_context,
            resolution_method="rules",
        )

    subject = _last_explicit_user_subject(request.history)
    has_alex_context = history_has_alex_assistant_context(request.history)

    if _is_follow_up_profile_question(normalized_message):
        if subject == "third_party":
            return QuestionResolution(
                intent="third_party_question",
                original_question=request.message,
                standalone_question=None,
                conversational_context=conversational_context,
                resolution_method="rules",
            )
        if subject == "alex" or has_alex_context:
            return QuestionResolution(
                intent="alex_profile_question",
                original_question=request.message,
                standalone_question=_resolve_alex_subject(request.message),
                conversational_context=conversational_context,
                resolution_method="rules",
            )

    contextualized_resolution = _try_llm_question_resolution(
        request=request,
        question_contextualizer=question_contextualizer,
        conversational_context=conversational_context,
    )
    if contextualized_resolution is not None:
        return contextualized_resolution

    if _looks_like_short_continuation(normalized_message):
        return _clarification_resolution(
            request=request,
            conversational_context=conversational_context,
            resolution_method="fallback",
        )

    if has_alex_context and _looks_like_short_profile_follow_up(normalized_message):
        return QuestionResolution(
            intent="alex_profile_question",
            original_question=request.message,
            standalone_question=_resolve_alex_subject(request.message),
            conversational_context=conversational_context,
            resolution_method="rules",
        )

    return QuestionResolution(
        intent="out_of_scope_question",
        original_question=request.message,
        standalone_question=None,
        conversational_context=conversational_context,
        resolution_method="rules",
    )


def format_conversation_context(history: list[ChatHistoryMessage]) -> str:
    lines = []
    for item in history:
        content = " ".join(item.content.split())
        lines.append(f"{item.role}: {content}")
    return "\n".join(lines)


def is_weakness_request(
    message: str,
    history: list[ChatHistoryMessage],
) -> bool:
    normalized_message = normalize_message(message)
    if route_query(message).intent != "public_boundary":
        return False
    if is_direct_third_party_subject(normalized_message):
        return False
    if _contains_any_phrase(normalized_message, ALEX_TERMS):
        return True
    if _contains_any_phrase(normalized_message, SECOND_PERSON_TERMS):
        return True
    if _contains_any_phrase(normalized_message, FOLLOW_UP_PRONOUN_TERMS):
        return history_has_alex_assistant_context(history)
    return False


def is_service_request(message: str) -> bool:
    normalized_message = normalize_message(message)
    return any(term in normalized_message for term in SERVICE_REQUEST_TERMS)


def should_offer_handoff_after_answer(message: str) -> bool:
    return _is_contact_or_availability_question(message) or is_service_request(message)


def handoff_reason_after_answer(message: str) -> str | None:
    if is_service_request(message):
        return "service_enquiry"
    if _is_contact_or_availability_question(message):
        return "user_requested_human"
    return None


def is_alex_specific_question(message: str) -> bool:
    normalized_message = normalize_message(message)
    if any(term in normalized_message for term in ALEX_TERMS):
        return True
    if _looks_like_profile_topic(normalized_message):
        return True
    return bool(
        any(term in normalized_message for term in SECOND_PERSON_TERMS)
        and any(term in normalized_message for term in ALEX_PROFILE_TERMS)
    )


def is_direct_third_party_subject(normalized_message: str) -> bool:
    if any(term in normalized_message for term in ALEX_TERMS):
        return False
    return any(subject in normalized_message for subject in KNOWN_THIRD_PARTY_SUBJECTS)


def history_has_alex_assistant_context(history: list[ChatHistoryMessage]) -> bool:
    owner_markers = _owner_context_markers()
    for item in reversed(history):
        if item.role != "assistant":
            continue
        normalized_content = normalize_message(item.content)
        if any(marker in normalized_content for marker in owner_markers):
            return True
    return False


def _try_llm_question_resolution(
    *,
    request: ChatRequest,
    question_contextualizer: QuestionContextualizer | None,
    conversational_context: str,
) -> QuestionResolution | None:
    if question_contextualizer is None:
        return None
    if not _should_contextualize_with_llm(request):
        return None

    try:
        contextualized = question_contextualizer.contextualize(
            message=request.message,
            conversational_context=conversational_context,
        )
    except (ProviderConfigurationError, ProviderRequestError):
        return None

    if contextualized.intent == "clarification_required" or contextualized.confidence == "low":
        return _clarification_resolution(
            request=request,
            conversational_context=conversational_context,
            resolution_method="llm",
        )

    return QuestionResolution(
        intent=contextualized.intent,
        original_question=request.message,
        standalone_question=(
            contextualized.standalone_question.strip()
            if contextualized.standalone_question
            else None
        ),
        conversational_context=conversational_context,
        resolution_method="llm",
    )


def _clarification_resolution(
    *,
    request: ChatRequest,
    conversational_context: str,
    resolution_method: QuestionResolutionMethod,
) -> QuestionResolution:
    return QuestionResolution(
        intent="clarification_required",
        original_question=request.message,
        standalone_question=None,
        conversational_context=conversational_context,
        resolution_method=resolution_method,
    )


def _is_contact_or_availability_question(message: str) -> bool:
    normalized_message = normalize_message(message)
    return any(term in normalized_message for term in CONTACT_OR_AVAILABILITY_TERMS)


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
    return any(term in normalized_message for term in EDUCATION_PROFILE_TERMS) or any(
        term in normalized_message for term in RAG_PROJECT_TERMS
    )


def _should_contextualize_with_llm(request: ChatRequest) -> bool:
    normalized_message = normalize_message(request.message)
    if any(term in normalized_message for term in ALEX_TERMS):
        return False
    is_ambiguous_follow_up = _looks_like_short_continuation(normalized_message) or any(
        term in normalized_message for term in FOLLOW_UP_PRONOUN_TERMS
    )
    if not is_ambiguous_follow_up:
        return False
    return history_has_alex_assistant_context(request.history)


def _last_explicit_user_subject(history: list[ChatHistoryMessage]) -> str | None:
    for item in reversed(history):
        if item.role != "user":
            continue
        normalized_content = normalize_message(item.content)
        if any(subject in normalized_content for subject in KNOWN_THIRD_PARTY_SUBJECTS):
            return "third_party"
        if any(term in normalized_content for term in ALEX_TERMS):
            return "alex"
    return None


def _owner_context_markers() -> tuple[str, ...]:
    owner_markers = set(ALEX_TERMS)
    owner_markers.add(normalize_message(_PROJECT_CONFIG.assistant.display_name))
    owner_markers.add(normalize_message(UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER))
    owner_markers.add(normalize_message(UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER))

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


def _resolve_alex_subject(message: str) -> str:
    normalized_message = normalize_message(message)
    if _contains_any_phrase(normalized_message, ALEX_TERMS):
        return message

    replacements = {
        "he": _OWNER_REFERENCE,
        "him": _OWNER_REFERENCE,
        "his": _OWNER_POSSESSIVE,
        "you": _OWNER_REFERENCE,
        "your": _OWNER_POSSESSIVE,
        "yours": _OWNER_POSSESSIVE,
    }
    resolved = _OWNER_PRONOUN_PATTERN.sub(
        lambda match: replacements[match.group(0).casefold()],
        message,
    )
    if resolved != message:
        return resolved
    return f"About {_OWNER_REFERENCE}: {message}"


def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    text_tokens = text.split()
    for phrase in phrases:
        phrase_tokens = normalize_message(phrase).split()
        width = len(phrase_tokens)
        if width and any(
            _tokens_match_phrase(text_tokens[index : index + width], phrase_tokens)
            for index in range(len(text_tokens) - width + 1)
        ):
            return True
    return False


def _tokens_match_phrase(text_tokens: list[str], phrase_tokens: list[str]) -> bool:
    if text_tokens == phrase_tokens:
        return True
    return bool(
        text_tokens[:-1] == phrase_tokens[:-1] and text_tokens[-1] == f"{phrase_tokens[-1]}'s"
    )
