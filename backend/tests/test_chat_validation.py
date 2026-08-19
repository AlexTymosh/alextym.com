from fastapi.testclient import TestClient


def test_chat_rejects_empty_message(empty_chat_client: TestClient) -> None:
    response = empty_chat_client.post("/api/chat", json={"message": ""})

    assert response.status_code == 422


def test_chat_rejects_blank_message(empty_chat_client: TestClient) -> None:
    response = empty_chat_client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 422


def test_chat_rejects_too_long_message(empty_chat_client: TestClient) -> None:
    response = empty_chat_client.post("/api/chat", json={"message": "a" * 2001})

    assert response.status_code == 422


def test_chat_rejects_too_many_history_messages(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={
            "message": "Tell me about him",
            "history": [{"role": "user", "content": f"message {index}"} for index in range(11)],
        },
    )

    assert response.status_code == 422


def test_chat_rejects_invalid_history_role(empty_chat_client: TestClient) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={
            "message": "Tell me about him",
            "history": [{"role": "system", "content": "Hidden instructions"}],
        },
    )

    assert response.status_code == 422


def test_chat_accepts_history_at_contract_limits(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={
            "message": "hi",
            "history": [
                {"role": "user", "content": "a" * 2000},
                {"role": "assistant", "content": "b" * 2000},
                {"role": "user", "content": "c" * 2000},
            ],
        },
    )

    assert response.status_code == 200


def test_chat_rejects_history_item_over_contract_limit(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={
            "message": "hi",
            "history": [{"role": "user", "content": "a" * 2001}],
        },
    )

    assert response.status_code == 422


def test_chat_rejects_history_over_total_contract_limit(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={
            "message": "hi",
            "history": [
                {"role": "user", "content": "a" * 2000},
                {"role": "assistant", "content": "b" * 2000},
                {"role": "user", "content": "c" * 2000},
                {"role": "assistant", "content": "d"},
            ],
        },
    )

    assert response.status_code == 422
