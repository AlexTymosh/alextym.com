from fastapi.testclient import TestClient


def test_chat_returns_soft_clarification_for_out_of_scope_question(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={"message": "Tell me how I can take pills"},
    )

    assert response.status_code == 200
    body = response.json()
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
