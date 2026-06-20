from fastapi.testclient import TestClient


def test_chat_returns_clarification_response_for_insufficient_data(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={"message": "Tell me about Alex's recent projects"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "not have enough reliable information" in body["answer"]
    assert "connect you with Alex" in body["answer"]
    assert body["sources"] == []
    assert body["confidence"] == "low"
    assert body["not_enough_data"] is True
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "insufficient_data"
    assert body["language_unsupported"] is False
    assert body["user_requested_human"] is False


def test_chat_handles_greeting_without_insufficient_data(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 200
    body = response.json()
    assert "digital assistant" in body["answer"]
    assert body["confidence"] == "high"
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is False
    assert body["handoff_reason"] is None
    assert body["language_unsupported"] is False
    assert body["user_requested_human"] is False
    assert body["sources"] == []


def test_chat_handles_good_afternoon_as_greeting(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post("/api/chat", json={"message": "Good afternoon"})

    assert response.status_code == 200
    body = response.json()
    assert body["not_enough_data"] is False
    assert "digital assistant" in body["answer"]


def test_chat_handles_intro_request_without_retrieval(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={"message": "Introduce yourself"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is False
    assert body["sources"] == []
    assert "Alex's digital assistant" in body["answer"]


def test_chat_handles_social_acknowledgement_without_out_of_scope(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
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
    assert body["answer"] == "OK. How else can I help?"
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is False
    assert body["language_unsupported"] is False
    assert body["user_requested_human"] is False
    assert body["sources"] == []
