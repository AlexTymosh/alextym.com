import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.llm.client import LLMClient, ProviderConfigurationError, ProviderRequestError
from app.llm.factory import get_configured_llm_client
from app.rag.factory import get_configured_retriever
from app.rag.models import KnowledgeChunk
from app.rag.prompt_builder import PromptBuilder
from app.rag.retriever import Retriever
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

        try:
            chunks = self._retriever.retrieve(request.message)
        except (ProviderConfigurationError, ProviderRequestError):
            return ChatResponse(
                answer=INSUFFICIENT_DATA_ANSWER,
                sources=[],
                confidence="low",
                not_enough_data=True,
            )

        if chunks:
            prompt = self._prompt_builder.build(question=request.message, chunks=chunks)
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
