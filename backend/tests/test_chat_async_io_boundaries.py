"""Chat event-loop and stream-closure regressions without external providers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from threading import Event
from types import SimpleNamespace

from app.api.chat import chat
from app.domain.chat_stream import ChatStreamEvent
from app.llm.openai_client import OpenAIResponsesClient
from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.prompt_builder import PromptBundle
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService
from app.services.chat_metrics import MetricsChatService, MetricsLLMClient

QUESTION = "Describe your automation projects."


def _chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        id="project-test",
        content="The Owner builds APIs, integrations and grounded RAG applications.",
        metadata=ChunkMetadata(
            source="resume.md",
            section="Projects",
            topic="projects",
            source_confidence="high",
            tags=("project", "automation"),
            extra={"retrieval_score": 0.95},
        ),
    )


class StaticRetriever:
    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeChunk]:
        return [_chunk()]


class BlockingRetriever:
    def __init__(self, entered: Event, release: Event):
        self.entered = entered
        self.release = release

    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeChunk]:
        self.entered.set()
        if not self.release.wait(2.0):
            raise TimeoutError("Retrieval worker did not release")
        return [_chunk()]


class BlockingAnswerService:
    def __init__(self, entered: Event, release: Event):
        self.entered = entered
        self.release = release

    def answer(self, request: ChatRequest) -> ChatResponse:
        self.entered.set()
        if not self.release.wait(2.0):
            raise TimeoutError("JSON answer worker did not release")
        return ChatResponse(answer="Done", confidence="high", not_enough_data=False)


def test_json_chat_offloads_blocking_answer() -> None:
    entered, release = Event(), Event()

    async def scenario() -> None:
        task = asyncio.create_task(
            chat(
                ChatRequest(message="hi"),
                _=None,
                service=BlockingAnswerService(entered, release),
            )
        )
        try:
            assert await asyncio.to_thread(entered.wait, 1.0)
            await asyncio.wait_for(asyncio.sleep(0), timeout=0.2)
            assert not task.done()
        finally:
            release.set()
        result = await asyncio.wait_for(task, timeout=3.0)
        assert result.answer == "Done"

    asyncio.run(scenario())


def test_stream_retrieval_does_not_block_other_coroutines() -> None:
    entered, release = Event(), Event()
    service = ChatService(retriever=BlockingRetriever(entered, release))

    async def collect() -> list[ChatStreamEvent]:
        return [event async for event in service.stream_answer(ChatRequest(message=QUESTION))]

    async def scenario() -> None:
        task = asyncio.create_task(collect())
        try:
            assert await asyncio.to_thread(entered.wait, 1.0)
            await asyncio.wait_for(asyncio.sleep(0), timeout=0.2)
            assert not task.done()
        finally:
            release.set()
        events = await asyncio.wait_for(task, timeout=3.0)
        assert events[0].event == "meta"
        assert events[-1].event == "done"

    asyncio.run(scenario())


class BlockingTokens:
    def __init__(self, entered: Event, release: Event):
        self.entered = entered
        self.release = release
        self.closed = Event()
        self.first = True

    def __iter__(self) -> Iterator[str]:
        return self

    def __next__(self) -> str:
        if not self.first:
            raise StopIteration
        self.first = False
        self.entered.set()
        if not self.release.wait(2.0):
            raise TimeoutError("Streaming token worker did not release")
        return "Grounded response. " * 25

    def close(self) -> None:
        self.closed.set()


class StreamingClient:
    def __init__(self, tokens: BlockingTokens):
        self.tokens = tokens

    def stream_answer(self, prompt: PromptBundle) -> Iterator[str]:
        return self.tokens

    def answer(self, prompt: PromptBundle) -> str:
        raise AssertionError("Streaming should not invoke a separate answer")


def test_sync_llm_next_runs_off_loop_and_closes_on_stream_cancel() -> None:
    entered, release = Event(), Event()
    tokens = BlockingTokens(entered, release)
    service = ChatService(retriever=StaticRetriever(), llm_client=StreamingClient(tokens))

    async def scenario() -> None:
        stream = service.stream_answer(ChatRequest(message=QUESTION))
        assert (await anext(stream)).event == "meta"
        next_event = asyncio.create_task(anext(stream))
        try:
            assert await asyncio.to_thread(entered.wait, 1.0)
            await asyncio.wait_for(asyncio.sleep(0), timeout=0.2)
            assert not next_event.done()
        finally:
            release.set()
        emitted = await asyncio.wait_for(next_event, timeout=3.0)
        assert emitted.event == "token"
        await stream.aclose()
        assert tokens.closed.is_set()

    asyncio.run(scenario())


class BlockingFallbackClient:
    # Not callable: this client supports only the synchronous answer API.
    stream_answer = None

    def __init__(self, entered: Event, release: Event):
        self.entered = entered
        self.release = release

    def answer(self, prompt: PromptBundle) -> str:
        self.entered.set()
        if not self.release.wait(2.0):
            raise TimeoutError("Fallback LLM worker did not release")
        return "A grounded answer."


def test_streaming_json_fallback_offloads_sync_llm_answer() -> None:
    entered, release = Event(), Event()
    service = ChatService(
        retriever=StaticRetriever(), llm_client=BlockingFallbackClient(entered, release)
    )

    async def collect() -> list[ChatStreamEvent]:
        return [event async for event in service.stream_answer(ChatRequest(message=QUESTION))]

    async def scenario() -> None:
        task = asyncio.create_task(collect())
        try:
            assert await asyncio.to_thread(entered.wait, 1.0)
            await asyncio.wait_for(asyncio.sleep(0), timeout=0.2)
            assert not task.done()
        finally:
            release.set()
        events = await asyncio.wait_for(task, timeout=3.0)
        assert events[-1].event == "done"
        assert any(event.event == "token" for event in events)

    asyncio.run(scenario())


def test_metrics_wrapper_closes_nested_chat_stream() -> None:
    class Source:
        closed = False

        async def stream_answer(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
            try:
                yield ChatStreamEvent("meta", {"status": "started"})
                yield ChatStreamEvent("token", {"text": "Hello"})
            finally:
                self.closed = True

    async def scenario() -> None:
        source = Source()
        wrapped = MetricsChatService(source)
        stream = wrapped.stream_answer(ChatRequest(message="hi"))
        assert (await anext(stream)).event == "meta"
        await stream.aclose()
        assert source.closed

    asyncio.run(scenario())


def test_metrics_llm_closes_underlying_iterator() -> None:
    class Source:
        closed = False

        def stream_answer(self, prompt: PromptBundle) -> Iterator[str]:
            try:
                yield "hello"
                yield "world"
            finally:
                self.closed = True

    provider = Source()
    tokens = MetricsLLMClient(provider).stream_answer(
        PromptBundle(system="system", context="context", question="question")
    )
    assert next(tokens) == "hello"
    tokens.close()
    assert provider.closed


def test_openai_adapter_closes_http_stream_on_early_generator_close() -> None:
    class ProviderStream:
        closed = False

        def __iter__(self) -> Iterator[SimpleNamespace]:
            yield SimpleNamespace(type="response.output_text.delta", delta="Hello")
            yield SimpleNamespace(type="response.output_text.delta", delta="World")

        def close(self) -> None:
            self.closed = True

    upstream = ProviderStream()
    client = OpenAIResponsesClient(
        api_key="",
        model="test-model",
        max_output_tokens=100,
        reasoning_effort="low",
        client=SimpleNamespace(responses=SimpleNamespace(create=lambda **_: upstream)),
    )
    stream = client.stream_answer(
        PromptBundle(system="system", context="context", question="question")
    )
    assert next(stream) == "Hello"
    stream.close()
    assert upstream.closed
