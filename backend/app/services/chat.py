import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.llm.client import LLMClient, ProviderConfigurationError, ProviderRequestError
from app.llm.factory import get_configured_llm_client
from app.rag.factory import get_configured_retriever
from app.rag.models import KnowledgeChunk
from app.rag.prompt_builder import PromptBuilder
from app.rag.retriever import Retriever
from app.schemas.chat import ChatHistoryMessage, ChatRequest, ChatResponse

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

GREETING_ANSWER = (
    "Hi, I'm Alex's digital assistant. You can ask me about Alex's backend work, "
    "RAG projects, automation, professional experience, or general software topics."
)

HELP_ANSWER = (
    "I can help in two ways:\n"
    "- For questions about Alex, I use Alex's public knowledge base and show sources when "
    "available.\n"
    "- For general software or technology questions, I can answer like a normal AI chat without "
    "claiming unsupported facts about Alex."
)

GENERAL_CHAT_UNAVAILABLE_ANSWER = (
    "I can answer general questions, but the AI model is temporarily unavailable. Please try "
    "again later."
)

PRIVATE_DATA_ANSWER = (
    "I can't provide private personal information. I can answer questions about Alex's public "
    "professional profile, skills, projects, and experience."
)

SCOPE_BOUNDARY_ANSWER = (
    "I'm focused on Alex's professional profile. I can help with Alex's experience, projects, "
    "skills, or general software topics."
)

GREETING_PATTERNS = (
    "hi",
    "hello",
    "hey",
    "how are you",
    "привет",
    "здравствуйте",
    "добрый день",
    "добрый вечер",
    "как дела",
)

HELP_PATTERNS = (
    "help",
    "what can you do",
    "what can i ask",
    "how can you help",
    "что ты умеешь",
    "чем ты можешь помочь",
    "что можно спросить",
)

PRIVATE_DATA_PATTERNS = (
    "private phone",
    "phone number",
    "personal email",
    "private email",
    "home address",
    "health",
    "medical",
    "colleague",
    "manager",
    "friend",
    "family",
    "телефон",
    "личный email",
    "личный имейл",
    "адрес",
    "здоровье",
    "медицин",
    "коллег",
    "руковод",
    "друз",
    "семь",
)

ALEX_TERMS = (
    "alex",
    "alextym",
    "tymosh",
    "tymoshenko",
    "алекс",
    "тимош",
    "тимошенко",
)

ALEX_PROFILE_TERMS = (
    "experience",
    "skill",
    "skills",
    "project",
    "projects",
    "resume",
    "cv",
    "education",
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
    "опыт",
    "навык",
    "проект",
    "резюме",
    "образован",
    "работ",
    "карьер",
    "профил",
    "саммари",
    "интро",
    "портфолио",
    "гитхаб",
    "линкедин",
    "контакт",
)

SECOND_PERSON_TERMS = (
    "you",
    "your",
    "yours",
    "ты",
    "твой",
    "твоя",
    "твои",
    "вы",
    "ваш",
    "ваша",
    "ваши",
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
    "tell",
    "work",
)

KNOWN_THIRD_PARTY_SUBJECTS = ("elon musk",)


@dataclass(frozen=True)
class QuestionResolution:
    is_alex_specific: bool
    retrieval_query: str
    conversational_context: str
    is_out_of_scope_subject: bool = False


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
        if self._looks_like_prompt_injection(request.message):
            return ChatResponse(
                answer=PROMPT_INJECTION_ANSWER,
                sources=[],
                confidence="low",
                not_enough_data=True,
            )

        if self._is_private_data_request(request.message):
            return ChatResponse(
                answer=PRIVATE_DATA_ANSWER,
                sources=[],
                confidence="low",
                not_enough_data=True,
            )

        if self._is_greeting(request.message):
            return ChatResponse(
                answer=GREETING_ANSWER,
                sources=[],
                confidence="medium",
                not_enough_data=False,
            )

        if self._is_help_request(request.message):
            return ChatResponse(
                answer=HELP_ANSWER,
                sources=[],
                confidence="medium",
                not_enough_data=False,
            )

        resolution = self._resolve_question(request)
        if resolution.is_out_of_scope_subject:
            return ChatResponse(
                answer=SCOPE_BOUNDARY_ANSWER,
                sources=[],
                confidence="medium",
                not_enough_data=False,
            )

        if not resolution.is_alex_specific:
            return self._answer_general_chat(
                request.message,
                conversational_context=resolution.conversational_context,
            )

        try:
            chunks = self._retriever.retrieve(resolution.retrieval_query)
        except (ProviderConfigurationError, ProviderRequestError):
            return ChatResponse(
                answer=INSUFFICIENT_DATA_ANSWER,
                sources=[],
                confidence="low",
                not_enough_data=True,
            )

        if chunks:
            prompt = self._prompt_builder.build(
                question=request.message,
                chunks=chunks,
                conversational_context=resolution.conversational_context,
            )
            answer = self._answer_from_prompt(prompt, chunks)
            return ChatResponse(
                answer=answer,
                sources=[
                    {
                        "title": chunk.metadata.source,
                        "section": chunk.metadata.section,
                        "confidence": chunk.metadata.source_confidence,
                    }
                    for chunk in chunks
                ],
                confidence="medium",
                not_enough_data=False,
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
    def _is_greeting(message: str) -> bool:
        normalized_message = _normalize_message(message)
        return normalized_message in GREETING_PATTERNS

    @staticmethod
    def _is_help_request(message: str) -> bool:
        normalized_message = _normalize_message(message)
        return any(pattern in normalized_message for pattern in HELP_PATTERNS)

    @staticmethod
    def _is_private_data_request(message: str) -> bool:
        normalized_message = _normalize_message(message)
        if not any(term in normalized_message for term in ALEX_TERMS + SECOND_PERSON_TERMS):
            return False
        return any(pattern in normalized_message for pattern in PRIVATE_DATA_PATTERNS)

    @staticmethod
    def _is_alex_specific_question(message: str) -> bool:
        normalized_message = _normalize_message(message)
        if any(term in normalized_message for term in ALEX_TERMS):
            return True
        if any(term in normalized_message for term in SECOND_PERSON_TERMS) and any(
            term in normalized_message for term in ALEX_PROFILE_TERMS
        ):
            return True
        return False

    @staticmethod
    def _resolve_question(request: ChatRequest) -> QuestionResolution:
        conversational_context = _format_conversation_context(request.history)
        normalized_message = _normalize_message(request.message)

        if _is_direct_third_party_subject(normalized_message):
            return QuestionResolution(
                is_alex_specific=False,
                retrieval_query=request.message,
                conversational_context=conversational_context,
                is_out_of_scope_subject=True,
            )

        if ChatService._is_alex_specific_question(request.message):
            return QuestionResolution(
                is_alex_specific=True,
                retrieval_query=_rewrite_alex_retrieval_query(request.message),
                conversational_context=conversational_context,
            )

        if _is_follow_up_profile_question(normalized_message):
            subject = _last_explicit_user_subject(request.history)
            if subject == "third_party":
                return QuestionResolution(
                    is_alex_specific=False,
                    retrieval_query=request.message,
                    conversational_context=conversational_context,
                    is_out_of_scope_subject=True,
                )
            if subject == "alex" or _history_has_alex_assistant_context(request.history):
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

    @staticmethod
    def _extractive_answer(chunks: list[KnowledgeChunk], context: str) -> str:
        if not context.strip():
            return INSUFFICIENT_DATA_ANSWER

        excerpts = [_first_sentence(chunk.content) for chunk in chunks[:2]]
        excerpts = [excerpt for excerpt in excerpts if excerpt]
        if not excerpts:
            return INSUFFICIENT_DATA_ANSWER

        if len(excerpts) == 1:
            return f"According to Alex's public knowledge base, {excerpts[0]}"

        return "According to Alex's public knowledge base, " + " ".join(
            f"{index}. {excerpt}" for index, excerpt in enumerate(excerpts, start=1)
        )

    def _answer_from_prompt(self, prompt: Any, chunks: list[KnowledgeChunk]) -> str:
        if self._llm_client is None:
            return self._extractive_answer(chunks, prompt.context)

        try:
            return self._llm_client.answer(prompt)
        except (ProviderConfigurationError, ProviderRequestError):
            return self._extractive_answer(chunks, prompt.context)

    def _answer_general_chat(
        self,
        message: str,
        *,
        conversational_context: str = "",
    ) -> ChatResponse:
        if self._llm_client is None:
            return ChatResponse(
                answer=GENERAL_CHAT_UNAVAILABLE_ANSWER,
                sources=[],
                confidence="low",
                not_enough_data=False,
            )

        prompt = self._prompt_builder.build_general_chat(
            question=message,
            conversational_context=conversational_context,
        )
        try:
            answer = self._llm_client.answer(prompt)
        except (ProviderConfigurationError, ProviderRequestError):
            answer = GENERAL_CHAT_UNAVAILABLE_ANSWER
            confidence = "low"
        else:
            confidence = "medium"

        return ChatResponse(
            answer=answer,
            sources=[],
            confidence=confidence,
            not_enough_data=False,
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


def _first_sentence(text: str, max_length: int = 360) -> str:
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


def _normalize_message(message: str) -> str:
    return " ".join(message.casefold().strip(" \t\r\n.,!?;:\u2026").split())


def _format_conversation_context(history: list[ChatHistoryMessage]) -> str:
    lines = []
    for item in history:
        content = " ".join(item.content.split())
        if len(content) > 500:
            content = content[:497].rstrip() + "..."
        lines.append(f"{item.role}: {content}")
    return "\n".join(lines)


def _is_direct_third_party_subject(normalized_message: str) -> bool:
    if any(term in normalized_message for term in ALEX_TERMS):
        return False
    return any(subject in normalized_message for subject in KNOWN_THIRD_PARTY_SUBJECTS)


def _is_follow_up_profile_question(normalized_message: str) -> bool:
    tokens = set(normalized_message.split())
    if not tokens.intersection(FOLLOW_UP_PRONOUN_TERMS):
        return False
    return bool(tokens.intersection(FOLLOW_UP_PROFILE_TERMS))


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
    for item in reversed(history):
        if item.role != "assistant":
            continue
        normalized_content = _normalize_message(item.content)
        if "alex's digital assistant" in normalized_content:
            return True
    return False


def _rewrite_alex_retrieval_query(message: str) -> str:
    normalized_message = _normalize_message(message)
    if normalized_message == "tell me about him":
        return "Tell me about Alex's professional background, experience, skills, and projects."
    if normalized_message == "what does he do":
        return "What does Alex do professionally?"
    if "your" in normalized_message and "project" in normalized_message:
        return "Tell me about Alex's professional projects and software work."
    if _is_follow_up_profile_question(normalized_message):
        return "Tell me about Alex's professional background, experience, skills, and projects."
    return message
