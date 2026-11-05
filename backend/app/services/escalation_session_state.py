"""Legacy imports for escalation state; domain owns the implementation.

Keep this module as a pure re-export until all external consumers have moved.
No independent dataclasses or transition functions may be defined here.
"""

from app.domain.escalation_session import (
    ESCALATION_SESSION_STATE_CLOSED,
    ESCALATION_SESSION_STATE_CONNECTED,
    ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
    EscalationSessionRecord,
    EscalationSessionTransition,
    build_append_alex_message_transition,
    build_close_session_transition,
    build_initial_session_record,
    remaining_ttl_seconds,
)

__all__ = [
    "ESCALATION_SESSION_STATE_CLOSED",
    "ESCALATION_SESSION_STATE_CONNECTED",
    "ESCALATION_SESSION_STATE_WAITING_FOR_ALEX",
    "EscalationSessionRecord",
    "EscalationSessionTransition",
    "build_append_alex_message_transition",
    "build_close_session_transition",
    "build_initial_session_record",
    "remaining_ttl_seconds",
]
