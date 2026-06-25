from collections.abc import Callable
from dataclasses import dataclass

from app.core.project_config import get_project_config
from app.schemas.chat import ChatHistoryMessage, ChatRequest, ChatResponse
from app.services.chat_copy import (
    ASSISTANT_INTRO_ANSWER,
    GREETING_ANSWER,
    HANDOFF_REQUEST_ANSWER,
    HELP_ANSWER,
    LANGUAGE_FALLBACK_ANSWERS,
    PRIVATE_DATA_ANSWER,
    PROMPT_INJECTION_ANSWER,
    PUBLIC_BOUNDARY_WEAKNESSES_ANSWER,
    SOCIAL_ACKNOWLEDGEMENT_ANSWER,
)
from app.services.chat_language import (
    LanguageStatus,
    detect_unsupported_language,
    normalize_message,
)
from app.services.chat_patterns import (
    ASSISTANT_INTRO_PATTERNS,
    GREETING_PATTERNS,
    HELP_PATTERNS,
    PRIVATE_DATA_ALEX_TERMS,
    PRIVATE_DATA_PATTERNS,
    SOCIAL_ACKNOWLEDGEMENT_PATTERNS,
)
from app.services.chat_safety import is_prompt_injection_attempt

_CHAT_LANGUAGE_RESTRICTIONS = get_project_config().chat.language_restrictions

LANGUAGE_RESTRICTIONS_BY_STATUS = {
    "russian": _CHAT_LANGUAGE_RESTRICTIONS.russian,
    "ukrainian": _CHAT_LANGUAGE_RESTRICTIONS.ukrainian,
    "other": _CHAT_LANGUAGE_RESTRICTIONS.other_non_english,
}

HandoffRequestPredicate = Callable[[str], bool]
HandoffConfirmationPredicate = Callable[[ChatRequest], bool]
WeaknessRequestPredicate = Callable[[str, list[ChatHistoryMessage]], bool]


@dataclass(frozen=True)
class ChatPolicyResult:
    intent: str
    response: ChatResponse


def apply_pre_rag_policy(
    request: ChatRequest,
    *,
    is_handoff_request: HandoffRequestPredicate,
    is_handoff_confirmation_after_prompt: HandoffConfirmationPredicate,
    is_weakness_request: WeaknessRequestPredicate,
) -> ChatPolicyResult | None:
    message = request.message

    if is_prompt_injection_attempt(message):
        return ChatPolicyResult(
            intent="prompt_injection",
            response=prompt_injection_response(),
        )

    if is_handoff_request(message):
        return ChatPolicyResult(
            intent="handoff_request",
            response=handoff_request_response(),
        )

    if is_handoff_confirmation_after_prompt(request):
        return ChatPolicyResult(
            intent="handoff_confirmation",
            response=handoff_request_response(),
        )

    language_status = detect_unsupported_language(message)
    if language_status is not None and LANGUAGE_RESTRICTIONS_BY_STATUS[language_status].enabled:
        return ChatPolicyResult(
            intent="language_unsupported",
            response=_language_unsupported_response(language_status),
        )

    if _is_private_data_request(message):
        return ChatPolicyResult(
            intent="private_data",
            response=ChatResponse(
                answer=PRIVATE_DATA_ANSWER,
                sources=[],
                confidence="low",
                not_enough_data=True,
                handoff_suggested=True,
                handoff_reason="private_data",
            ),
        )

    if is_weakness_request(message, request.history):
        return ChatPolicyResult(
            intent="public_boundary_weaknesses",
            response=ChatResponse(
                answer=PUBLIC_BOUNDARY_WEAKNESSES_ANSWER,
                sources=[],
                confidence="high",
                not_enough_data=False,
                handoff_suggested=True,
                handoff_reason="public_boundary",
            ),
        )

    if _is_greeting(message):
        return ChatPolicyResult(
            intent="greeting",
            response=ChatResponse(
                answer=GREETING_ANSWER,
                sources=[],
                confidence="high",
                not_enough_data=False,
            ),
        )

    if _is_help_request(message):
        return ChatPolicyResult(
            intent="help",
            response=ChatResponse(
                answer=HELP_ANSWER,
                sources=[],
                confidence="high",
                not_enough_data=False,
            ),
        )

    if _is_assistant_intro_request(message):
        return ChatPolicyResult(
            intent="assistant_intro",
            response=ChatResponse(
                answer=ASSISTANT_INTRO_ANSWER,
                sources=[],
                confidence="high",
                not_enough_data=False,
            ),
        )

    if _is_social_acknowledgement(message):
        return ChatPolicyResult(
            intent="social_acknowledgement",
            response=ChatResponse(
                answer=SOCIAL_ACKNOWLEDGEMENT_ANSWER,
                sources=[],
                confidence="high",
                not_enough_data=False,
            ),
        )

    return None


def prompt_injection_response() -> ChatResponse:
    return ChatResponse(
        answer=PROMPT_INJECTION_ANSWER,
        sources=[],
        confidence="low",
        not_enough_data=True,
        handoff_suggested=False,
    )


def handoff_request_response() -> ChatResponse:
    return ChatResponse(
        answer=HANDOFF_REQUEST_ANSWER,
        sources=[],
        confidence="high",
        not_enough_data=False,
        handoff_suggested=True,
        handoff_reason="user_requested_human",
        user_requested_human=True,
    )


def _language_unsupported_response(language_status: LanguageStatus) -> ChatResponse:
    return ChatResponse(
        answer=LANGUAGE_FALLBACK_ANSWERS[language_status],
        sources=[],
        confidence="medium",
        not_enough_data=False,
        handoff_suggested=True,
        handoff_reason="language_unsupported",
        language_unsupported=True,
    )


def _is_greeting(message: str) -> bool:
    return normalize_message(message) in GREETING_PATTERNS


def _is_help_request(message: str) -> bool:
    normalized_message = normalize_message(message)
    return any(pattern in normalized_message for pattern in HELP_PATTERNS)


def _is_assistant_intro_request(message: str) -> bool:
    normalized_message = normalize_message(message)
    return any(pattern in normalized_message for pattern in ASSISTANT_INTRO_PATTERNS)


def _is_social_acknowledgement(message: str) -> bool:
    return normalize_message(message) in SOCIAL_ACKNOWLEDGEMENT_PATTERNS


def _is_private_data_request(message: str) -> bool:
    normalized_message = normalize_message(message)
    has_private_term = any(pattern in normalized_message for pattern in PRIVATE_DATA_PATTERNS)
    if not has_private_term:
        return False
    return any(term in normalized_message for term in PRIVATE_DATA_ALEX_TERMS)
