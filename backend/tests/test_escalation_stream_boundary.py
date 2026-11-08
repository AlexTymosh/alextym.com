"""Protect escalation application events and their existing SSE wire contract."""

from __future__ import annotations

import ast
import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.escalation import (
    _as_sse_item,
    get_escalation_service,
    router,
    stream_escalation_messages,
)
from app.api.sse import serialize_sse_item
from app.domain.escalation_stream import (
    EscalationHeartbeat,
    EscalationStreamEvent,
)
from app.services.escalation import EscalationService
from app.services.escalation_sessions import (
    ESCALATION_SESSION_STATE_CONNECTED,
    EscalationSessionRecord,
)

HANDOFF_ID = "hnd_" + "e" * 32
MESSAGE_1 = {
    "id": "msg_first",
    "role": "alex",
    "content": "First answer",
    "created_at": "2026-01-01T00:01:00+00:00",
}
MESSAGE_2 = {
    "id": "msg_second",
    "role": "alex",
    "content": "Second answer",
    "created_at": "2026-01-01T00:02:00+00:00",
}


def _record() -> EscalationSessionRecord:
    return EscalationSessionRecord(
        handoff_id=HANDOFF_ID,
        state=ESCALATION_SESSION_STATE_CONNECTED,
        created_at="2026-01-01T00:00:00+00:00",
        expires_at="2999-01-01T00:00:00+00:00",
        transcript=[{"role": "user", "content": "A public work enquiry"}],
        messages=[MESSAGE_1, MESSAGE_2],
    )


class SequenceStore:
    def __init__(self, records: list[EscalationSessionRecord | None]) -> None:
        self._records = list(records)

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        assert handoff_id == HANDOFF_ID
        return self._records.pop(0) if self._records else None


def _service(*, read_count: int, heartbeat: float = 60.0) -> EscalationService:
    record = _record()
    return EscalationService(
        notifier=None,
        session_store=SequenceStore([record] * read_count + [None]),
        stream_poll_interval_seconds=0.001,
        stream_heartbeat_interval_seconds=heartbeat,
    )


def _app(service: EscalationService) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_escalation_service] = lambda: service
    return app


def _json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def test_escalation_service_has_no_http_sse_imports() -> None:
    import app.domain.escalation_stream as domain_module
    import app.services.escalation as service_module

    for module in (domain_module, service_module):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert "app.schemas.sse" not in imports
        assert "app.api.sse" not in imports


def test_escalation_application_emits_logical_events_and_heartbeat() -> None:
    async def collect() -> list[object]:
        service = _service(read_count=1, heartbeat=0.0)
        return [event async for event in service.stream_alex_messages(HANDOFF_ID)]

    events = asyncio.run(collect())
    assert [type(item) for item in events] == [
        EscalationStreamEvent,
        EscalationStreamEvent,
        EscalationStreamEvent,
        EscalationHeartbeat,
        EscalationStreamEvent,
    ]
    assert [event.kind for event in events if isinstance(event, EscalationStreamEvent)] == [
        "meta",
        "message",
        "message",
        "closed",
    ]
    assert events[2].message_id == "msg_second"
    assert events[-1].payload == {"reason": "session_expired"}


def test_escalation_adapter_golden_sse_message_and_comment_bytes() -> None:
    message = EscalationStreamEvent("message", MESSAGE_2, message_id="msg_second")
    heartbeat = EscalationHeartbeat()
    assert serialize_sse_item(_as_sse_item(message)) == (
        "id: msg_second\nevent: message\ndata: " + _json(MESSAGE_2) + "\n\n"
    )
    assert serialize_sse_item(_as_sse_item(heartbeat)) == ": heartbeat\n\n"


def test_escalation_http_stream_preserves_exact_event_bytes() -> None:
    with TestClient(_app(_service(read_count=2))) as client:
        response = client.get(f"/api/escalations/{HANDOFF_ID}/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.text == (
        "event: meta\ndata: "
        + _json({"handoff_id": HANDOFF_ID, "status": "connected"})
        + "\n\n"
        + "id: msg_first\nevent: message\ndata: "
        + _json(MESSAGE_1)
        + "\n\n"
        + "id: msg_second\nevent: message\ndata: "
        + _json(MESSAGE_2)
        + "\n\n"
        + 'event: closed\ndata: {"reason":"session_expired"}\n\n'
    )


def test_escalation_http_stream_replays_after_last_event_id() -> None:
    with TestClient(_app(_service(read_count=3))) as client:
        response = client.get(
            f"/api/escalations/{HANDOFF_ID}/stream",
            headers={"Last-Event-ID": "msg_first"},
        )

    assert response.status_code == 200
    assert "msg_first" not in response.text
    assert response.text == (
        "event: meta\ndata: "
        + _json({"handoff_id": HANDOFF_ID, "status": "connected"})
        + "\n\n"
        + "id: msg_second\nevent: message\ndata: "
        + _json(MESSAGE_2)
        + "\n\n"
        + 'event: closed\ndata: {"reason":"session_expired"}\n\n'
    )


def test_disconnection_closes_underlying_service_stream() -> None:
    class TrackingService:
        closed = False

        async def ensure_stream_available(self, handoff_id: str) -> None:
            assert handoff_id == HANDOFF_ID

        async def stream_alex_messages(
            self, handoff_id: str, *, after_message_id: str | None = None
        ) -> AsyncIterator[EscalationStreamEvent]:
            try:
                yield EscalationStreamEvent("meta", {"handoff_id": handoff_id})
                yield EscalationStreamEvent("closed", {"reason": "session_closed"})
            finally:
                self.closed = True

    class DisconnectedRequest:
        async def is_disconnected(self) -> bool:
            return True

    async def scenario() -> None:
        service = TrackingService()
        response = await stream_escalation_messages(
            HANDOFF_ID,
            request=DisconnectedRequest(),
            last_event_id=None,
            service=service,
        )
        emitted = [item async for item in response.body_iterator]
        assert emitted == []
        assert service.closed is True

    asyncio.run(scenario())
