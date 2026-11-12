"""Characterize Chat event-to-SSE framing without calling external providers."""

from __future__ import annotations

import ast
import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import chat_stream, get_chat_service, router
from app.api.rate_limit import enforce_chat_rate_limit
from app.api.sse import serialize_sse_item, sse_event
from app.domain.chat_stream import ChatStreamEvent
from app.rag.retriever import EmptyRetriever
from app.schemas.chat import ChatRequest
from app.schemas.sse import ServerSentEvent
from app.services.chat import ChatService


EVENTS = (
    ChatStreamEvent("meta", {"request_id": "test-id", "status": "started"}),
    ChatStreamEvent("token", {"text": "Caf\u00e9, Owner"}),
    ChatStreamEvent("sources", {"sources": []}),
    ChatStreamEvent("done", {"request_id": "test-id", "confidence": "high"}),
)


class ScriptedChatService:
    async def stream_answer(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        assert request.message == "hello"
        for event in EVENTS:
            yield event


class FailingChatService:
    async def stream_answer(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        raise RuntimeError("private provider diagnostic")
        yield ChatStreamEvent("token", {"text": "unreachable"})


def _app(service: object) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_chat_service] = lambda: service
    app.dependency_overrides[enforce_chat_rate_limit] = lambda: None
    return app


def test_domain_event_has_no_sse_framing_or_event_id() -> None:
    event = EVENTS[1]
    assert isinstance(event, ChatStreamEvent)
    assert event.event == "token"
    assert event.data == {"text": "Caf\u00e9, Owner"}
    assert not isinstance(event, ServerSentEvent)
    assert not hasattr(event, "event_id")


def test_domain_event_serializes_to_the_existing_sse_wire_format() -> None:
    for event in EVENTS:
        assert sse_event(event.event, event.data) == serialize_sse_item(
            ServerSentEvent(event.event, event.data)
        )


def test_chat_http_adapter_preserves_exact_event_order_and_bytes() -> None:
    with TestClient(_app(ScriptedChatService())) as client:
        response = client.post("/api/chat/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.text == "".join(sse_event(event.event, event.data) for event in EVENTS)
    assert "Caf\u00e9" in response.text  # Preserve non-ASCII payloads.
    assert "id: " not in response.text  # Chat has no SSE event IDs.


def test_chat_http_adapter_keeps_safe_streaming_error_event() -> None:
    with TestClient(_app(FailingChatService())) as client:
        response = client.post("/api/chat/stream", json={"message": "hello"})
    assert response.status_code == 200
    assert response.text == sse_event(
        "error", {"message": "Something went wrong. Please try again later."}
    )
    assert "private provider diagnostic" not in response.text


def test_chat_service_emits_domain_events_not_transport_frames() -> None:
    async def collect() -> list[ChatStreamEvent]:
        service = ChatService(retriever=EmptyRetriever())
        return [event async for event in service.stream_answer(ChatRequest(message="hi"))]

    events = asyncio.run(collect())
    assert events[0].event == "meta"
    assert events[-1].event == "done"
    assert all(isinstance(event, ChatStreamEvent) for event in events)
    assert all(not isinstance(event, ServerSentEvent) for event in events)


def test_client_disconnect_stops_stream_before_emitting_next_event() -> None:
    class DisconnectedRequest:
        calls = 0

        async def is_disconnected(self) -> bool:
            self.calls += 1
            return True

    async def collect() -> tuple[list[str], int]:
        request = DisconnectedRequest()
        response = await chat_stream(
            ChatRequest(message="hello"), request=request, _=None, service=ScriptedChatService()
        )
        return [item async for item in response.body_iterator], request.calls

    data, calls = asyncio.run(collect())
    assert data == []
    assert calls == 1


def test_application_services_do_not_import_sse_transport() -> None:
    import app.domain.chat_stream as domain_module
    import app.services.chat as service_module
    import app.services.chat_metrics as metrics_module

    for module in (service_module, metrics_module):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert "app.schemas.sse" not in imports
        assert "app.api.sse" not in imports

    tree = ast.parse(Path(domain_module.__file__).read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.")
        for node in ast.walk(tree)
    )
