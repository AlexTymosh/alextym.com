from fastapi.testclient import TestClient

from tests.chat_expected_responses import INSUFFICIENT_DATA_ANSWER


def test_chat_routes_reusable_owner_reference_to_profile_context(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={"message": "How did the Owner automate WEEE reporting?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == INSUFFICIENT_DATA_ANSWER
    assert body["sources"] == []
    assert body["not_enough_data"] is True
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "insufficient_data"
