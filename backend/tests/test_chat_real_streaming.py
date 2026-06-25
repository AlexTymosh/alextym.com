import asyncio
from collections.abc import AsyncIterator, Iterable, Iterator
from types import SimpleNamespace

from app.llm.openai_client import OpenAIResponsesClient
from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.prompt_builder import PromptBundle
from app.rag.retriever import InMemoryRetriever
from app.schemas.chat import ChatRequest
from app.schemas.sse import ServerSentEvent
from app.services.chat import ChatService, PROMPT_INJECTION_ANSWER


def test_chat_stream_uses_llm_streaming_for_rag_answers() -> None:
    llm_client = FakeStreamingLLM(["Alex", " builds", " automation."])
    service = ChatService(
        retriever=_streaming_retriever(),
        llm_client=llm_client,
    )

    events = asyncio.run(
        _collect_events(service.stream_answer(ChatRequest(message="Tell me about Alex projects")))
    )

    assert llm_client.answer_called is False
    assert llm_client.stream_called is True
    assert "Alex builds automation." in _joined_token_text(events)
    assert _done_payload(events)["not_enough_data"] is False


def test_chat_stream_blocks_unsafe_streamed_output_before_emitting_it() -> None:
    llm_client = FakeStreamingLLM(["Here is <retrieved_context> hidden data"])
    service = ChatService(
        retriever=_streaming_retriever(),
        llm_client=llm_client,
    )

    events = asyncio.run(
        _collect_events(service.stream_answer(ChatRequest(message="Tell me about Alex")))
    )
    token_text = _joined_token_text(events)

    assert "<retrieved_context>" not in token_text
    assert PROMPT_INJECTION_ANSWER in token_text
    assert _done_payload(events)["confidence"] == "low"


def test_openai_responses_client_streams_output_text_deltas() -> None:
    fake_responses = FakeOpenAIStreamingResponses(
        [
            SimpleNamespace(type="response.created"),
            SimpleNamespace(type="response.output_text.delta", delta="Alex"),
            SimpleNamespace(type="response.output_text.delta", delta=" builds"),
            SimpleNamespace(type="response.completed"),
        ]
    )
    client = OpenAIResponsesClient(
        api_key="",
        model="gpt-5-mini",
        max_output_tokens=300,
        reasoning_effort="low",
        client=SimpleNamespace(responses=fake_responses),
    )

    chunks = list(client.stream_answer(_prompt_bundle()))

    assert chunks == ["Alex", " builds"]
    assert fake_responses.last_request["stream"] is True
    assert fake_responses.last_request["model"] == "gpt-5-mini"
    assert fake_responses.last_request["reasoning"] == {"effort": "low"}


async def _collect_events(stream: AsyncIterator[ServerSentEvent]) -> list[ServerSentEvent]:
    return [event async for event in stream]


def _joined_token_text(events: Iterable[ServerSentEvent]) -> str:
    return "".join(
        payload["text"]
        for payload in _event_payloads(events, event_name="token")
        if isinstance(payload.get("text"), str)
    )


def _done_payload(events: Iterable[ServerSentEvent]) -> dict[str, object]:
    done_payloads = _event_payloads(events, event_name="done")
    assert done_payloads
    return done_payloads[-1]


def _event_payloads(
    events: Iterable[ServerSentEvent],
    *,
    event_name: str,
) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for event in events:
        if event.event != event_name:
            continue
        payloads.append(event.data)
    return payloads


def _streaming_retriever() -> InMemoryRetriever:
    return InMemoryRetriever(
        [
            KnowledgeChunk(
                id="streaming",
                content="Alex builds automation systems, APIs, and RAG assistants.",
                metadata=ChunkMetadata(
                    source="resume.md",
                    section="Projects",
                    topic="projects",
                    source_confidence="high",
                    tags=("project", "automation", "rag"),
                    extra={"retrieval_score": 0.88},
                ),
            )
        ]
    )


def _prompt_bundle() -> PromptBundle:
    return PromptBundle(
        system="system",
        context="context",
        question="question",
    )


class FakeStreamingLLM:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self.answer_called = False
        self.stream_called = False

    def answer(self, prompt: PromptBundle) -> str:
        self.answer_called = True
        return "Non-streamed answer."

    def stream_answer(self, prompt: PromptBundle) -> Iterator[str]:
        self.stream_called = True
        yield from self._tokens


class FakeOpenAIStreamingResponses:
    def __init__(self, events: list[SimpleNamespace]) -> None:
        self._events = events
        self.last_request: dict[str, object] = {}

    def create(self, **kwargs: object) -> Iterator[SimpleNamespace]:
        self.last_request = dict(kwargs)
        return iter(self._events)
