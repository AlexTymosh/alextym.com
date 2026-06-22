from fastapi.testclient import TestClient

HANDOFF_REQUEST_ANSWER = "I can connect you with Alex directly. Please confirm below to continue."


def test_chat_accepts_non_english_handoff_request_before_language_guard(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
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


def test_chat_accepts_handoff_request_with_connect_typo(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post("/api/chat", json={"message": "connnect me"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == HANDOFF_REQUEST_ANSWER
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "user_requested_human"
    assert body["user_requested_human"] is True


def test_chat_accepts_confirmation_after_handoff_prompt(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
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
