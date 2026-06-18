import json
from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.chat import get_chat_service
from app.main import app
from app.rag.retriever import EmptyRetriever
from app.services.chat import ChatService, GREETING_ANSWER

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_chat_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_chat_stream_returns_sse_policy_response() -> None:
    app.dependency_overrides[get_chat_service] = lambda: ChatService(retriever=EmptyRetriever())

    response, body = _post_stream({"message": "hi"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert "event: meta" in body
    assert "event: token" in body
    assert "event: sources" in body
    assert "event: done" in body
    assert _joined_token_text(body) == GREETING_ANSWER
    assert _last_payload(body, "done")["confidence"] == "high"


def test_chat_stream_returns_safe_error_event_for_service_failure() -> None:
    app.dependency_overrides[get_chat_service] = lambda: BrokenStreamingService()

    response, body = _post_stream({"message": "Tell me about Alex"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert _last_payload(body, "error") == {
        "message": "Something went wrong. Please try again later."
    }
    assert "provider exploded" not in body


def _post_stream(payload: dict[str, object]) -> tuple[object, str]:
    with client.stream("POST", "/api/chat/stream", json=payload) as response:
        body = "".join(response.iter_text())
    return response, body


def _joined_token_text(body: str) -> str:
    return "".join(
        payload["text"]
        for payload in _event_payloads(body, event_name="token")
        if isinstance(payload.get("text"), str)
    )


def _last_payload(body: str, event_name: str) -> dict[str, object]:
    payloads = _event_payloads(body, event_name=event_name)
    assert payloads
    return payloads[-1]


def _event_payloads(body: str, *, event_name: str) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    current_event: str | None = None
    for line in body.splitlines():
        if line.startswith("event: "):
            current_event = line.removeprefix("event: ")
            continue
        if current_event != event_name or not line.startswith("data: "):
            continue
        payload = json.loads(line.removeprefix("data: "))
        assert isinstance(payload, dict)
        payloads.append(payload)
    return payloads


class BrokenStreamingService:
    async def stream_answer(self, request: object) -> AsyncIterator[str]:
        raise RuntimeError("provider exploded")
        # Keep this method as an async generator to match the streaming contract.
        yield ""
