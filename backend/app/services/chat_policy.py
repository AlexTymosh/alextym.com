from collections.abc import Callable
from dataclasses import dataclass

from app.core.project_config import get_project_config
from app.schemas.chat import ChatHistoryMessage, ChatRequest, ChatResponse
from app.services.chat_language import (
    LanguageStatus,
    detect_unsupported_language,
    normalize_message,
)
from app.services.chat_safety import is_prompt_injection_attempt

_PROJECT_CONFIG = get_project_config()
OWNER_REFERENCE = _PROJECT_CONFIG.assistant.owner_reference
OWNER_POSSESSIVE = _PROJECT_CONFIG.owner.possessive_name
_OWNER_RUSSIAN_NAME = _PROJECT_CONFIG.owner.russian_name
_OWNER_UKRAINIAN_NAME = _PROJECT_CONFIG.owner.ukrainian_name
ALEX_TERMS = tuple(
    dict.fromkeys(
        [
            OWNER_REFERENCE.casefold(),
            *(alias.casefold() for alias in _PROJECT_CONFIG.owner.public_aliases),
        ]
    )
)
_CHAT_LANGUAGE_RESTRICTIONS = _PROJECT_CONFIG.chat.language_restrictions

HANDOFF_PROMPT_TITLE = f"Would you like to connect with {OWNER_REFERENCE}?"

INSUFFICIENT_DATA_ANSWER = (
    "I do not have enough reliable information in the public knowledge base "
    "to answer that accurately. \n"
    f"Would you like me to connect you with {OWNER_REFERENCE}?"
)
PROMPT_INJECTION_ANSWER = (
    "I\u2019m not sure I can help with that request.\n"
    f"Let\u2019s focus on {OWNER_POSSESSIVE} professional background or "
    "collaboration options. \n"
    "Could you clarify what you\u2019d like to know?"
)
UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER = (
    "\u0418\u0437\u0432\u0438\u043d\u0438\u0442\u0435, "
    f"{_OWNER_RUSSIAN_NAME} "
    "\u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0438\u043b "
    "\u043c\u0435\u043d\u044f \u0432 \u043e\u0431\u0449\u0435\u043d\u0438\u0438 "
    "\u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c "
    "\u044f\u0437\u044b\u043a\u0435. \u042f \u043c\u043e\u0433\u0443 "
    "\u043e\u0442\u0432\u0435\u0447\u0430\u0442\u044c "
    "\u0442\u043e\u043b\u044c\u043a\u043e "
    "\u043f\u043e-\u0430\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u0438.\n"
    "\u0414\u043b\u044f \u043e\u0431\u0449\u0435\u043d\u0438\u044f "
    "\u043f\u043e-\u0440\u0443\u0441\u0441\u043a\u0438 \u044f "
    "\u043c\u043e\u0433\u0443 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0438\u0442\u044c "
    "\u043f\u0440\u044f\u043c\u043e\u0435 \u043e\u0431\u0449\u0435\u043d\u0438\u0435."
)
UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER = (
    "\u0412\u0438\u0431\u0430\u0447\u0442\u0435, "
    f"{_OWNER_UKRAINIAN_NAME} "
    "\u043e\u0431\u043c\u0435\u0436\u0438\u0432 \u043c\u0435\u043d\u0435 "
    "\u0443 \u0441\u043f\u0456\u043b\u043a\u0443\u0432\u0430\u043d\u043d\u0456 "
    "\u0443\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u043e\u044e "
    "\u043c\u043e\u0432\u043e\u044e. \u042f \u043c\u043e\u0436\u0443 "
    "\u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0434\u0430\u0442\u0438 "
    "\u043b\u0438\u0448\u0435 "
    "\u0430\u043d\u0433\u043b\u0456\u0439\u0441\u044c\u043a\u043e\u044e.\n"
    "\u042f\u043a\u0449\u043e \u0432\u0430\u043c \u0437\u0440\u0443\u0447\u043d\u0456\u0448\u0435 "
    "\u0441\u043f\u0456\u043b\u043a\u0443\u0432\u0430\u0442\u0438\u0441\u044f "
    "\u0440\u0456\u0434\u043d\u043e\u044e \u043c\u043e\u0432\u043e\u044e, "
    "\u044f \u043c\u043e\u0436\u0443 "
    "\u0437\u0430\u043f\u0440\u043e\u043f\u043e\u043d\u0443\u0432\u0430\u0442\u0438 "
    "\u043f\u0440\u044f\u043c\u0435 \u0437\u0432\u0435\u0440\u043d\u0435\u043d\u043d\u044f."
)
UNSUPPORTED_NON_ENGLISH_ANSWER = (
    f"Sorry, {OWNER_REFERENCE} has limited me to English.\n"
    "Please ask your question in English, or use the contact option below "
    f"to reach {OWNER_REFERENCE} directly."
)
OUT_OF_SCOPE_ANSWER = (
    "To help you best, could you clarify your request?\n"
    f"I handle professional enquiries about {OWNER_POSSESSIVE} expertise "
    "and background.\n"
    f"You can also type 'connect me with {OWNER_REFERENCE}' to reach "
    "them directly."
)
HANDOFF_REQUEST_ANSWER = (
    f"I can connect you with {OWNER_REFERENCE} directly. Please confirm below to continue."
)
PUBLIC_BOUNDARY_WEAKNESSES_ANSWER = (
    "Thank you for the deeper interest.\n"
    f"{OWNER_REFERENCE} prefers to discuss their weaknesses directly rather "
    "than through a public assistant.\n"
    "I can share verified information about their professional background, "
    f"or you can type \u201cconnect me with {OWNER_REFERENCE}\u201d so I can "
    "connect you with them for a direct conversation.\n"
)
SOCIAL_ACKNOWLEDGEMENT_ANSWER = "OK. How else can I help?"
PRIVATE_DATA_ANSWER = PROMPT_INJECTION_ANSWER
GREETING_ANSWER = f"Hi. I\u2019m {OWNER_POSSESSIVE} digital assistant. How can I help you today?"
HELP_ANSWER = (
    f"You can ask about {OWNER_POSSESSIVE} experience, projects, software "
    "services, availability, or contact options."
)
ASSISTANT_INTRO_ANSWER = (
    f"I\u2019m {OWNER_POSSESSIVE} digital assistant. \n"
    f"I can tell you about {OWNER_POSSESSIVE} professional background."
)
LANGUAGE_FALLBACK_ANSWERS = {
    "russian": UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER,
    "ukrainian": UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER,
    "other": UNSUPPORTED_NON_ENGLISH_ANSWER,
}
LANGUAGE_RESTRICTIONS_BY_STATUS = {
    "russian": _CHAT_LANGUAGE_RESTRICTIONS.russian,
    "ukrainian": _CHAT_LANGUAGE_RESTRICTIONS.ukrainian,
    "other": _CHAT_LANGUAGE_RESTRICTIONS.other_non_english,
}

GREETING_PATTERNS = (
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "how do you do",
)

HELP_PATTERNS = (
    "help",
    "what can you do",
    "what can i ask",
    "how can you help",
)

ASSISTANT_INTRO_PATTERNS = (
    "introduce yourself",
    "who are you",
    "what are you",
    "tell me about yourself",
)

SOCIAL_ACKNOWLEDGEMENT_PATTERNS = (
    "cool",
    "nice",
    "great",
    "thanks",
    "thank you",
    "many thanks",
    "ok",
    "okay",
    "got it",
    "understood",
    "sounds good",
)

PRIVATE_DATA_PATTERNS = (
    "private phone",
    "phone number",
    "personal email",
    "private email",
    "home address",
    "private address",
)
PRIVATE_DATA_ALEX_TERMS = (*ALEX_TERMS, "his", "him", "you", "your")

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
