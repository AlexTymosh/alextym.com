from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.api.escalation import get_escalation_service
from app.main import app
from app.schemas.escalation import EscalationMessageRequest, EscalationRequest
from app.services.escalation import EscalationService
from app.services.handoff_availability import (
    HandoffAvailabilityStatus,
    HandoffUnavailableError,
    ScheduledHandoffAvailabilityChecker,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


def test_handoff_availability_allows_requests_inside_window() -> None:
    checker = _checker_at("2026-01-01T10:00:00+00:00")

    checker.ensure_available()


def test_handoff_availability_rejects_requests_before_window() -> None:
    checker = _checker_at("2026-01-01T08:59:00+00:00")

    with pytest.raises(HandoffUnavailableError) as exc_info:
        checker.ensure_available()

    assert exc_info.value.status.to_http_detail() == {
        "code": "handoff_outside_hours",
        "message": (
            "Live handoff is available from 09:00 to 21:00 Europe/London time. "
            "Please try again during those hours or use the contact form."
        ),
        "contact_path": "/contact",
        "start_time": "09:00",
        "end_time": "21:00",
        "timezone": "Europe/London",
    }


def test_handoff_availability_rejects_requests_at_end_of_window() -> None:
    checker = _checker_at("2026-01-01T21:00:00+00:00")

    with pytest.raises(HandoffUnavailableError):
        checker.ensure_available()


def test_handoff_availability_supports_overnight_windows() -> None:
    checker = ScheduledHandoffAvailabilityChecker(
        timezone_name="UTC",
        start_time="21:00",
        end_time="06:00",
        now_provider=lambda: datetime.fromisoformat("2026-01-01T23:00:00+00:00"),
    )

    checker.ensure_available()


def test_escalation_returns_403_when_handoff_is_outside_hours() -> None:
    notifier = FakeEscalationNotifier()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        availability_checker=ClosedHandoffAvailabilityChecker(),
    )

    response = client.post(
        "/api/escalations",
        json={
            "consent_accepted": True,
            "reason": "user_requested_human",
            "transcript": [{"role": "user", "content": "Can I speak to Alex?"}],
            "company_website": "",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": _closed_detail()}
    assert notifier.sent_requests == []


def test_escalation_message_returns_403_when_handoff_is_outside_hours() -> None:
    notifier = FakeEscalationNotifier()
    app.dependency_overrides[get_escalation_service] = lambda: EscalationService(
        notifier=notifier,
        availability_checker=ClosedHandoffAvailabilityChecker(),
    )

    response = client.post(
        "/api/escalations/hnd_test/messages",
        json={"content": "Hello", "company_website": ""},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": _closed_detail()}
    assert notifier.sent_message_requests == []


class ClosedHandoffAvailabilityChecker:
    def ensure_available(self) -> None:
        raise HandoffUnavailableError(
            HandoffAvailabilityStatus(
                is_available=False,
                start_time="09:00",
                end_time="21:00",
                timezone="Europe/London",
            )
        )


class FakeEscalationNotifier:
    def __init__(self) -> None:
        self.sent_requests: list[EscalationRequest] = []
        self.sent_message_requests: list[EscalationMessageRequest] = []

    async def notify(
        self,
        escalation_request: EscalationRequest,
        *,
        handoff_id: str | None,
    ) -> None:
        self.sent_requests.append(escalation_request)

    async def notify_user_message(
        self,
        message_request: EscalationMessageRequest,
        *,
        handoff_id: str,
    ) -> None:
        self.sent_message_requests.append(message_request)


def _checker_at(value: str) -> ScheduledHandoffAvailabilityChecker:
    return ScheduledHandoffAvailabilityChecker(
        timezone_name="Europe/London",
        start_time="09:00",
        end_time="21:00",
        now_provider=lambda: datetime.fromisoformat(value).astimezone(ZoneInfo("Europe/London")),
    )


def _closed_detail() -> dict[str, str]:
    return {
        "code": "handoff_outside_hours",
        "message": (
            "Live handoff is available from 09:00 to 21:00 Europe/London time. "
            "Please try again during those hours or use the contact form."
        ),
        "contact_path": "/contact",
        "start_time": "09:00",
        "end_time": "21:00",
        "timezone": "Europe/London",
    }
