from datetime import UTC, datetime, timedelta

from app.services.escalation_session_state import (
    ESCALATION_SESSION_STATE_CLOSED,
    ESCALATION_SESSION_STATE_CONNECTED,
    ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
    EscalationSessionRecord,
    build_append_alex_message_transition,
    build_close_session_transition,
    build_initial_session_record,
)


def test_build_initial_session_record_sets_waiting_state_and_expiry() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    record = build_initial_session_record(
        transcript=[{"role": "user", "content": "Can I speak to Alex?"}],
        ttl_seconds=120,
        now=now,
    )

    assert record.handoff_id.startswith("hnd_")
    assert record.state == ESCALATION_SESSION_STATE_WAITING_FOR_ALEX
    assert record.created_at == "2026-01-01T00:00:00+00:00"
    assert record.expires_at == "2026-01-01T00:02:00+00:00"
    assert record.transcript == [{"role": "user", "content": "Can I speak to Alex?"}]
    assert record.messages == []


def test_append_alex_message_transition_connects_session_and_preserves_ttl() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    record = _session_record(expires_at=now + timedelta(seconds=120))

    transition = build_append_alex_message_transition(
        record,
        "Hello from Alex",
        now=now,
    )

    assert transition.record is not None
    assert transition.record.state == ESCALATION_SESSION_STATE_CONNECTED
    assert transition.ttl_seconds == 120
    assert transition.should_delete is False
    assert transition.record.messages[0]["role"] == "alex"
    assert transition.record.messages[0]["content"] == "Hello from Alex"


def test_append_alex_message_transition_ignores_closed_session() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    record = _session_record(
        state=ESCALATION_SESSION_STATE_CLOSED,
        expires_at=now + timedelta(seconds=120),
    )

    transition = build_append_alex_message_transition(
        record,
        "Hello from Alex",
        now=now,
    )

    assert transition.record is None
    assert transition.ttl_seconds is None
    assert transition.should_delete is False


def test_close_session_transition_appends_optional_close_message() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    record = _session_record(expires_at=now + timedelta(seconds=120))

    transition = build_close_session_transition(
        record,
        close_message="This conversation has been closed.",
        now=now,
    )

    assert transition.record is not None
    assert transition.record.state == ESCALATION_SESSION_STATE_CLOSED
    assert transition.ttl_seconds == 120
    assert transition.should_delete is False
    assert transition.record.messages[0]["content"] == "This conversation has been closed."


def test_expired_session_transition_requests_delete() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    record = _session_record(expires_at=now - timedelta(seconds=1))

    transition = build_close_session_transition(record, now=now)

    assert transition.record is None
    assert transition.ttl_seconds is None
    assert transition.should_delete is True


def _session_record(
    *,
    state: str = ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
    expires_at: datetime,
) -> EscalationSessionRecord:
    return EscalationSessionRecord(
        handoff_id="hnd_test",
        state=state,
        created_at="2026-01-01T00:00:00+00:00",
        expires_at=expires_at.isoformat(),
        transcript=[{"role": "user", "content": "Can I speak to Alex?"}],
        messages=[],
    )
