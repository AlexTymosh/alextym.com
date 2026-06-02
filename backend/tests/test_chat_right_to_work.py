from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.retriever import InMemoryRetriever
from app.services.chat import ChatService, HANDOFF_REQUEST_ANSWER
from app.schemas.chat import ChatRequest


def test_right_to_work_question_suggests_handoff_with_rag_answer() -> None:
    service = ChatService(retriever=_right_to_work_retriever())

    response = service.answer(ChatRequest(message="Does Alex have the right to work in the UK?"))

    assert response.not_enough_data is False
    assert response.handoff_suggested is True
    assert response.handoff_reason == "user_requested_human"
    assert "Would you like to connect with Alex?" in response.answer


def test_work_authorisation_question_suggests_handoff() -> None:
    service = ChatService(retriever=_right_to_work_retriever())

    response = service.answer(ChatRequest(message="Can you confirm Alex's work authorisation?"))

    assert response.not_enough_data is False
    assert response.handoff_suggested is True
    assert response.handoff_reason == "user_requested_human"


def test_share_code_request_routes_to_handoff_immediately() -> None:
    service = ChatService(retriever=_right_to_work_retriever())

    response = service.answer(ChatRequest(message="I need Alex's share code"))

    assert response.answer == HANDOFF_REQUEST_ANSWER
    assert response.handoff_suggested is True
    assert response.handoff_reason == "user_requested_human"


def test_availability_question_keeps_handoff_suggestion() -> None:
    service = ChatService(retriever=_availability_retriever())

    response = service.answer(ChatRequest(message="When can Alex start a new job?"))

    assert response.not_enough_data is False
    assert response.handoff_suggested is True
    assert response.handoff_reason == "user_requested_human"
    assert "Would you like to connect with Alex?" in response.answer


def _right_to_work_retriever() -> InMemoryRetriever:
    return InMemoryRetriever(
        [
            KnowledgeChunk(
                id="resume:right-to-work-uk-location:rag",
                content=(
                    "Alex has the right to live and work in the United Kingdom. "
                    "Alex can provide a UK right-to-work share code upon request."
                ),
                metadata=ChunkMetadata(
                    source="resume.generated.chunks.json",
                    section="experience",
                    topic="right-to-work-uk-location",
                    tags=("right-to-work", "share-code", "uk-location"),
                ),
            )
        ]
    )


def _availability_retriever() -> InMemoryRetriever:
    return InMemoryRetriever(
        [
            KnowledgeChunk(
                id="resume:availability-start-date:rag",
                content=(
                    "Alex's exact start date and calendar availability should "
                    "be confirmed directly with Alex. The assistant does not "
                    "have access to Alex's live calendar."
                ),
                metadata=ChunkMetadata(
                    source="resume.generated.chunks.json",
                    section="experience",
                    topic="availability-start-date",
                    tags=("availability", "start-date", "contact"),
                ),
            )
        ]
    )
