import json
from dataclasses import dataclass

from app.core.project_config import get_project_config
from app.llm.client import LLMClient, ProviderConfigurationError, ProviderRequestError
from app.rag.prompt_builder import PromptBundle
from app.schemas.chat import ChatHistoryMessage, ChatRequest
from app.services.chat_language import normalize_message
from app.services.chat_policy import (
    ALEX_TERMS,
    UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER,
    UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER,
)

_PROJECT_CONFIG = get_project_config()
_OWNER_REFERENCE = _PROJECT_CONFIG.assistant.owner_reference
_OWNER_POSSESSIVE = _PROJECT_CONFIG.owner.possessive_name

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


def resolve_question(
    request: ChatRequest,
    *,
    llm_client: LLMClient | None,
) -> QuestionResolution:
    conversational_context = format_conversation_context(request.history)
    normalized_message = normalize_message(request.message)

    if is_direct_third_party_subject(normalized_message):
        return QuestionResolution(
            is_alex_specific=False,
            retrieval_query=request.message,
            conversational_context=conversational_context,
            is_out_of_scope_subject=True,
        )

    if is_alex_specific_question(request.message):
        return QuestionResolution(
            is_alex_specific=True,
            retrieval_query=_rewrite_alex_retrieval_query(request.message),
            conversational_context=conversational_context,
        )

    if is_service_request(request.message):
        return QuestionResolution(
            is_alex_specific=True,
            retrieval_query=_services_retrieval_query(),
            conversational_context=conversational_context,
        )

    subject = _last_explicit_user_subject(request.history)
    has_alex_context = history_has_alex_assistant_context(request.history)

    classifier_resolution = _try_llm_intent_resolution(
        request=request,
        llm_client=llm_client,
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


def format_conversation_context(history: list[ChatHistoryMessage]) -> str:
    lines = []
    for item in history:
        content = " ".join(item.content.split())
        if len(content) > 500:
            content = content[:497].rstrip() + "..."
        lines.append(f"{item.role}: {content}")
    return "\n".join(lines)


def is_weakness_request(
    message: str,
    history: list[ChatHistoryMessage],
) -> bool:
    normalized_message = normalize_message(message)
    if _looks_like_profile_topic(normalized_message):
        return False
    if not any(term in normalized_message for term in WEAKNESS_REQUEST_TERMS):
        return False
    if is_direct_third_party_subject(normalized_message):
        return False
    if any(term in normalized_message for term in ALEX_TERMS):
        return True
    if any(term in normalized_message for term in SECOND_PERSON_TERMS):
        return True
    if any(term in normalized_message for term in FOLLOW_UP_PRONOUN_TERMS):
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


def _try_llm_intent_resolution(
    *,
    request: ChatRequest,
    llm_client: LLMClient | None,
    conversational_context: str,
) -> QuestionResolution | None:
    if llm_client is None:
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
        raw_answer = llm_client.answer(prompt)
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
    normalized_message = normalize_message(request.message)
    if any(term in normalized_message for term in ALEX_TERMS):
        return False
    if not any(term in normalized_message for term in FOLLOW_UP_PRONOUN_TERMS):
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


def _rewrite_alex_retrieval_query(message: str) -> str:
    normalized_message = normalize_message(message)
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
