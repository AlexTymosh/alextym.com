import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

ESCALATION_SESSION_STATE_WAITING_FOR_ALEX = "waiting_for_alex"
ESCALATION_SESSION_STATE_CONNECTED = "connected"
ESCALATION_SESSION_STATE_CLOSED = "closed"


@dataclass(frozen=True)
class EscalationSessionRecord:
    handoff_id: str
    state: str
    created_at: str
    expires_at: str
    transcript: list[dict[str, str]]
    messages: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EscalationSessionRecord":
        transcript = payload.get("transcript")
        if not isinstance(transcript, list):
            transcript = []

        messages = payload.get("messages")
        if not isinstance(messages, list):
            messages = []

        return cls(
            handoff_id=str(payload["handoff_id"]),
            state=str(payload["state"]),
            created_at=str(payload["created_at"]),
            expires_at=str(payload["expires_at"]),
            transcript=[
                {
                    "role": str(item.get("role", "")),
                    "content": str(item.get("content", "")),
                }
                for item in transcript
                if isinstance(item, dict)
            ],
            messages=[
                {
                    "id": str(item.get("id", "")),
                    "role": str(item.get("role", "")),
                    "content": str(item.get("content", "")),
                    "created_at": str(item.get("created_at", "")),
                }
                for item in messages
                if isinstance(item, dict)
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "state": self.state,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "transcript": self.transcript,
            "messages": self.messages,
        }


@dataclass(frozen=True)
class EscalationSessionTransition:
    record: EscalationSessionRecord | None
    ttl_seconds: int | None = None
    should_delete: bool = False


def build_initial_session_record(
    *,
    transcript: list[dict[str, str]],
    ttl_seconds: int,
    now: datetime | None = None,
) -> EscalationSessionRecord:
    created_at = _normalise_now(now)
    expires_at = created_at + timedelta(seconds=ttl_seconds)
    return EscalationSessionRecord(
        handoff_id=_create_handoff_id(),
        state=ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
        created_at=created_at.isoformat(),
        expires_at=expires_at.isoformat(),
        transcript=transcript,
        messages=[],
    )


def build_append_alex_message_transition(
    record: EscalationSessionRecord,
    content: str,
    *,
    now: datetime | None = None,
) -> EscalationSessionTransition:
    if record.state == ESCALATION_SESSION_STATE_CLOSED:
        return EscalationSessionTransition(record=None)

    current_time = _normalise_now(now)
    ttl_seconds = remaining_ttl_seconds(record.expires_at, current_time)
    if ttl_seconds <= 0:
        return EscalationSessionTransition(record=None, should_delete=True)

    updated_record = replace(
        record,
        state=ESCALATION_SESSION_STATE_CONNECTED,
        messages=[
            *record.messages,
            _build_alex_message(content, current_time),
        ],
    )
    return EscalationSessionTransition(
        record=updated_record,
        ttl_seconds=ttl_seconds,
    )


def build_close_session_transition(
    record: EscalationSessionRecord,
    *,
    close_message: str | None = None,
    now: datetime | None = None,
) -> EscalationSessionTransition:
    if record.state == ESCALATION_SESSION_STATE_CLOSED:
        return EscalationSessionTransition(record=record)

    current_time = _normalise_now(now)
    ttl_seconds = remaining_ttl_seconds(record.expires_at, current_time)
    if ttl_seconds <= 0:
        return EscalationSessionTransition(record=None, should_delete=True)

    messages = record.messages
    if close_message:
        messages = [*record.messages, _build_alex_message(close_message, current_time)]

    updated_record = replace(
        record,
        state=ESCALATION_SESSION_STATE_CLOSED,
        messages=messages,
    )
    return EscalationSessionTransition(
        record=updated_record,
        ttl_seconds=ttl_seconds,
    )


def remaining_ttl_seconds(expires_at: str, now: datetime) -> int:
    expires_at_datetime = datetime.fromisoformat(expires_at)
    if expires_at_datetime.tzinfo is None:
        expires_at_datetime = expires_at_datetime.replace(tzinfo=UTC)

    return int((expires_at_datetime - now).total_seconds())


def _normalise_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.replace(microsecond=0)


def _build_alex_message(content: str, created_at: datetime) -> dict[str, str]:
    return {
        "id": _create_message_id(),
        "role": "alex",
        "content": content,
        "created_at": created_at.isoformat(),
    }


def _create_handoff_id() -> str:
    return f"hnd_{uuid.uuid4().hex}"


def _create_message_id() -> str:
    return f"msg_{uuid.uuid4().hex}"
