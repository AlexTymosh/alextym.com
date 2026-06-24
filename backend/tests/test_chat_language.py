from fastapi.testclient import TestClient

from tests.chat_expected_responses import (
    INSUFFICIENT_DATA_ANSWER,
    UNSUPPORTED_NON_ENGLISH_ANSWER,
    UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER,
    UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER,
)


def test_chat_blocks_russian_language_with_handoff(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={
            "message": "\u0420\u0430\u0441\u0441\u043a\u0430\u0436\u0438 \u043f\u0440\u043e \u0410\u043b\u0435\u043a\u0441\u0430"
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


def test_chat_blocks_ukrainian_language_with_handoff(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={
            "message": "\u0420\u043e\u0437\u043a\u0430\u0436\u0438 \u043f\u0440\u043e \u041e\u043b\u0435\u043a\u0441\u0456\u044f"
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


def test_chat_blocks_likely_non_english_latin_language_with_handoff(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={"message": "Hola, puede Alex ayudar con automatizaci\u00f3n?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == UNSUPPORTED_NON_ENGLISH_ANSWER
    assert body["sources"] == []
    assert body["confidence"] == "medium"
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "language_unsupported"
    assert body["language_unsupported"] is True
    assert body["user_requested_human"] is False


def test_chat_does_not_block_foreign_brand_name_in_english(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={"message": "Can Alex work with M\u00fcller GmbH systems?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == INSUFFICIENT_DATA_ANSWER
    assert body["language_unsupported"] is False
    assert body["handoff_reason"] == "insufficient_data"
