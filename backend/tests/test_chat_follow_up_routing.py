from fastapi.testclient import TestClient


def test_chat_treats_yes_after_alex_follow_up_as_continuation(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
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
    assert "not have enough reliable information" in body["answer"]
    assert body["handoff_reason"] == "insufficient_data"


def test_chat_routes_mba_follow_up_to_alex_context(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
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
    assert "not have enough reliable information" in body["answer"]
    assert body["handoff_reason"] == "insufficient_data"


def test_chat_routes_university_follow_up_to_alex_context(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
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
    assert "not have enough reliable information" in body["answer"]
    assert body["handoff_reason"] == "insufficient_data"
