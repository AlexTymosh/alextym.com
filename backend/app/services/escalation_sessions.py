from app.core.config import Settings
from app.repositories.escalation_session_store import (
    EscalationSessionStore,
    EscalationSessionStoreError,
    MisconfiguredEscalationSessionStore,
)
from app.repositories.upstash_escalation_session_store import (
    UpstashRedisEscalationSessionStore,
)
from app.services.escalation_session_state import (
    ESCALATION_SESSION_STATE_CLOSED,
    ESCALATION_SESSION_STATE_CONNECTED,
    ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
    EscalationSessionRecord,
)

__all__ = [
    "ESCALATION_SESSION_STATE_WAITING_FOR_ALEX",
    "ESCALATION_SESSION_STATE_CONNECTED",
    "ESCALATION_SESSION_STATE_CLOSED",
    "EscalationSessionRecord",
    "EscalationSessionStore",
    "EscalationSessionStoreError",
    "MisconfiguredEscalationSessionStore",
    "UpstashRedisEscalationSessionStore",
    "build_escalation_session_store",
]


def build_escalation_session_store(settings: Settings) -> EscalationSessionStore | None:
    upstash_values = (
        settings.upstash_redis_rest_url,
        settings.upstash_redis_rest_token,
    )
    if all(upstash_values):
        return UpstashRedisEscalationSessionStore(
            rest_url=settings.upstash_redis_rest_url,
            rest_token=settings.upstash_redis_rest_token,
        )
    if any(upstash_values):
        return MisconfiguredEscalationSessionStore()

    return None
