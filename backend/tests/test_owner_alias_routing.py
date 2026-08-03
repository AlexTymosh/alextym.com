from fastapi.testclient import TestClient

from tests.chat_expected_responses import INSUFFICIENT_DATA_ANSWER


def test_chat_routes_reusable_site_owner_reference_to_profile_context(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={"message": "How did the site owner automate WEEE reporting?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == INSUFFICIENT_DATA_ANSWER
    assert body["sources"] == []
    assert body["not_enough_data"] is True
    assert body["handoff_suggested"] is True
    assert body["handoff_reason"] == "insufficient_data"


def test_chat_does_not_route_external_owner_question_to_profile_context(
    empty_chat_client: TestClient,
) -> None:
    response = empty_chat_client.post(
        "/api/chat",
        json={"message": "Who is the owner of GitHub?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "clarify your request" in body["answer"]
    assert body["sources"] == []
    assert body["not_enough_data"] is False
    assert body["handoff_suggested"] is False
    assert body["handoff_reason"] is None
