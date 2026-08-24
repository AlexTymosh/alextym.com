import asyncio

from app.rag.errors import RetrievalError
from app.schemas.chat import ChatRequest
from app.services.chat import ChatService, RETRIEVAL_UNAVAILABLE_ANSWER


def test_chat_distinguishes_retrieval_failure_from_empty_knowledge() -> None:
    service = ChatService(retriever=FailingRetriever())

    response = service.answer(ChatRequest(message="Tell me about Alex's projects"))

    assert response.answer == RETRIEVAL_UNAVAILABLE_ANSWER
    assert response.sources == []
    assert response.not_enough_data is False
    assert response.retrieval_status == "unavailable"
    assert response.handoff_suggested is False
    assert response.handoff_reason is None


def test_stream_done_event_exposes_same_retrieval_failure_status() -> None:
    service = ChatService(retriever=FailingRetriever())

    events = asyncio.run(
        _collect_events(service.stream_answer(ChatRequest(message="Tell me about Alex's projects")))
    )
    done = next(event.data for event in events if event.event == "done")
    answer = "".join(event.data["text"] for event in events if event.event == "token")

    assert answer == RETRIEVAL_UNAVAILABLE_ANSWER
    assert done["not_enough_data"] is False
    assert done["retrieval_status"] == "unavailable"
    assert done["handoff_suggested"] is False


class FailingRetriever:
    def retrieve(self, query: str, *, limit: int = 6) -> list[object]:
        raise RetrievalError(
            "Provider detail that must not reach the response.",
            stage="vector_search",
            code="vector_search_failed",
            retryable=True,
        )


async def _collect_events(stream: object) -> list[object]:
    return [event async for event in stream]
