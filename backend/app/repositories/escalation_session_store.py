from typing import Protocol

from app.services.escalation_session_state import EscalationSessionRecord


class EscalationSessionStoreError(Exception):
    pass


class EscalationSessionStore(Protocol):
    async def create(
        self,
        session_record: EscalationSessionRecord,
        *,
        ttl_seconds: int,
    ) -> EscalationSessionRecord:
        pass

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        pass

    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        pass

    async def close(
        self,
        handoff_id: str,
        *,
        close_message: str | None = None,
    ) -> EscalationSessionRecord | None:
        pass

    async def delete(self, handoff_id: str) -> None:
        pass


class MisconfiguredEscalationSessionStore:
    async def create(
        self,
        session_record: EscalationSessionRecord,
        *,
        ttl_seconds: int,
    ) -> EscalationSessionRecord:
        raise EscalationSessionStoreError("Redis session storage is partially configured.")

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("Redis session storage is partially configured.")

    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("Redis session storage is partially configured.")

    async def close(
        self,
        handoff_id: str,
        *,
        close_message: str | None = None,
    ) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("Redis session storage is partially configured.")

    async def delete(self, handoff_id: str) -> None:
        raise EscalationSessionStoreError("Redis session storage is partially configured.")
