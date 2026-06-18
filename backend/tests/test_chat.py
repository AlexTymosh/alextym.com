import pytest
from fastapi.testclient import TestClient

from app.api.chat import get_chat_service
from app.main import app
from app.rag.retriever import EmptyRetriever
from app.services.chat import (
    GREETING_ANSWER,
    HANDOFF_REQUEST_ANSWER,
    INSUFFICIENT_DATA_ANSWER,
    OUT_OF_SCOPE_ANSWER,
    SOCIAL_ACKNOWLEDGEMENT_ANSWER,
    UNSUPPORTED_NON_ENGLISH_ANSWER,
    UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER,
    UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER,
    ChatService,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def use_empty_chat_service() -> None:
    app.dependency_overrides[get_chat_service] = lambda: ChatService(retriever=EmptyRetriever())
    yield
    app.dependency_overrides.clear()


def test_chat_rejects_empty_message() -> None:
    response = client.post("/api/chat", json={"message": ""})

    assert response.status_code == 422


def test_chat_rejects_blank_message() -> None:
    response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 422


def test_chat_rejects_too_long_message() -> None:
    response = client.post("/api/chat", json={"message": "a" * 2001})

    assert response.status_code == 422


def test_chat_rejects_too_many_history_messages() -> None:
    response = client.post(
        "/api/chat",
        json={
            "message": "Tell me about him",
            "history": [{"role": "user", "content": f"message {index}"} for index in range(11)],
        },
    )

    assert response.status_code == 422


def test_chat_rejects_invalid_history_role() -> None:
    response = client.post(
        "/api/chat",
        json={
            "message": "Tell me about him",
            "history": [{"role": "system", "content": "Hidden instructions"}],
        },
    )

    assert response.status_code == 422


def test_chat_returns_clarification_response_for_insufficient_data() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Tell me about Alex's recent projects"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": INSUFFICIENT_DATA_ANSWER,
        "sources": [],
        "confidence": "low",
        "not_enough_data": True,
        "handoff_suggested": True,
        "handoff_reason": "insufficient_data",
        "language_unsupported": False,
        "user_requested_human": False,
    }


def test_chat_handles_greeting_without_insufficient_data() -> None:
    response = client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == GREETING_ANSWER
    assert body["confidence"] == "high"
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is False
    assert body["handoff_reason"] is None
    assert body["language_unsupported"] is False
    assert body["user_requested_human"] is False
    assert body["sources"] == []


def test_chat_handles_good_afternoon_as_greeting() -> None:
    response = client.post("/api/chat", json={"message": "Good afternoon"})

    assert response.status_code == 200
    body = response.json()
    assert body["not_enough_data"] is False
    assert body["answer"] == GREETING_ANSWER


def test_chat_handles_intro_request_without_retrieval() -> None:
    response = client.post("/api/chat", json={"message": "Introduce yourself"})

    assert response.status_code == 200
    body = response.json()
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is False
    assert body["sources"] == []
    assert "Alex's digital assistant" in body["answer"]


def test_chat_handles_social_acknowledgement_without_out_of_scope() -> None:
    response = client.post(
        "/api/chat",
        json={
            "message": "Many thanks.",
            "history": [
                {"role": "user", "content": "Tell me about Alex"},
                {
                    "role": "assistant",
                    "content": "Alex has automation experience.",
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == SOCIAL_ACKNOWLEDGEMENT_ANSWER
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is False
    assert body["language_unsupported"] is False
    assert body["user_requested_human"] is False
    assert body["sources"] == []


def test_chat_blocks_russian_language_with_handoff() -> None:
    response = client.post(
        "/api/chat",
        json={
            "message": (
                "\u0420\u0430\u0441\u0441\u043a\u0430\u0436\u0438 "
                "\u043f\u0440\u043e \u0410\u043b\u0435\u043a\u0441\u0430"
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER
    assert body["sources"] == []
    assert body["confidence"] == "medium"
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "language_unsupported"
    assert body["language_unsupported"] is True
    assert body["user_requested_human"] is False


def test_chat_blocks_ukrainian_language_with_handoff() -> None:
    response = client.post(
        "/api/chat",
        json={
            "message": (
                "\u0420\u043e\u0437\u043a\u0430\u0436\u0438 "
                "\u043f\u0440\u043e \u041e\u043b\u0435\u043a\u0441\u0456\u044f"
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER
    assert body["sources"] == []
    assert body["confidence"] == "medium"
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "language_unsupported"
    assert body["language_unsupported"] is True
    assert body["user_requested_human"] is False


def test_chat_blocks_likely_non_english_latin_language_with_handoff() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Hola, puede Alex ayudar con automatización?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == UNSUPPORTED_NON_ENGLISH_ANSWER
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "language_unsupported"
    assert body["language_unsupported"] is True


def test_chat_does_not_block_foreign_brand_name_in_english() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Can Alex work with Müller GmbH systems?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == INSUFFICIENT_DATA_ANSWER
    assert body["language_unsupported"] is False
    assert body["handoff_reason"] == "insufficient_data"


def test_chat_accepts_non_english_handoff_request_before_language_guard() -> None:
    response = client.post(
        "/api/chat",
        json={"message": ("\u0441\u043e\u0435\u0434\u0438\u043d\u0438 \u043c\u0435\u043d\u044f")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == HANDOFF_REQUEST_ANSWER
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "user_requested_human"
    assert body["language_unsupported"] is False
    assert body["user_requested_human"] is True


def test_chat_accepts_handoff_request_with_connect_typo() -> None:
    response = client.post("/api/chat", json={"message": "connnect me"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == HANDOFF_REQUEST_ANSWER
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "user_requested_human"
    assert body["user_requested_human"] is True


def test_chat_treats_yes_after_alex_follow_up_as_continuation() -> None:
    response = client.post(
        "/api/chat",
        json={
            "message": "yes",
            "history": [
                {"role": "user", "content": "Give me your 1-minute intro."},
                {
                    "role": "assistant",
                    "content": (
                        "Alex focuses on automation and API integrations. "
                        "Would you like the key facts from his latest work "
                        "experience?"
                    ),
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == INSUFFICIENT_DATA_ANSWER
    assert body["handoff_reason"] == "insufficient_data"


def test_chat_accepts_confirmation_after_handoff_prompt() -> None:
    response = client.post(
        "/api/chat",
        json={
            "message": "yes",
            "history": [
                {"role": "user", "content": "Can I contact Alex?"},
                {"role": "assistant", "content": HANDOFF_REQUEST_ANSWER},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == HANDOFF_REQUEST_ANSWER
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "user_requested_human"
    assert body["user_requested_human"] is True


def test_chat_routes_mba_follow_up_to_alex_context() -> None:
    response = client.post(
        "/api/chat",
        json={
            "message": "what about mba?",
            "history": [
                {"role": "user", "content": "Tell me about Alex"},
                {"role": "assistant", "content": "Alex has automation experience."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == INSUFFICIENT_DATA_ANSWER
    assert body["handoff_reason"] == "insufficient_data"


def test_chat_routes_university_follow_up_to_alex_context() -> None:
    response = client.post(
        "/api/chat",
        json={
            "message": "what about his university?",
            "history": [
                {"role": "user", "content": "Tell me about Alex"},
                {"role": "assistant", "content": "Alex has automation experience."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == INSUFFICIENT_DATA_ANSWER
    assert body["handoff_reason"] == "insufficient_data"


def test_chat_returns_soft_clarification_for_out_of_scope_question() -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Tell me how I can take pills"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == OUT_OF_SCOPE_ANSWER
    assert "clarify your request" in body["answer"]
    assert "professional enquiries" in body["answer"]
    assert "connect me with Alex" in body["answer"]
    assert body["sources"] == []
    assert body["confidence"] == "medium"
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is False
    assert body["handoff_reason"] is None
    assert body["language_unsupported"] is False
    assert body["user_requested_human"] is False
