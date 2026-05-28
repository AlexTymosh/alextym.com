import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from starlette.concurrency import run_in_threadpool

from app.schemas.escalation import EscalationRequest

ESCALATION_SESSION_STATE_WAITING_FOR_ALEX = "waiting_for_alex"
ESCALATION_SESSION_KEY_PREFIX = "escalation:session:"


class EscalationSessionStoreError(Exception):
    pass


@dataclass(frozen=True)
class EscalationSessionRecord:
    handoff_id: str
    state: str
    created_at: str
    expires_at: str
    transcript: list[dict[str, str]]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EscalationSessionRecord":
        transcript = payload.get("transcript")
        if not isinstance(transcript, list):
            transcript = []

        return cls(
            handoff_id=str(payload["handoff_id"]),
            state=str(payload["state"]),
            created_at=str(payload["created_at"]),
            expires_at=str(payload["expires_at"]),
            transcript=[
                {"role": str(item.get("role", "")), "content": str(item.get("content", ""))}
                for item in transcript
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
        }


class EscalationSessionStore(Protocol):
    async def create(
        self,
        escalation_request: EscalationRequest,
        *,
        ttl_seconds: int,
    ) -> EscalationSessionRecord:
        pass

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        pass

    async def delete(self, handoff_id: str) -> None:
        pass


class MisconfiguredEscalationSessionStore:
    async def create(
        self,
        escalation_request: EscalationRequest,
        *,
        ttl_seconds: int,
    ) -> EscalationSessionRecord:
        raise EscalationSessionStoreError("Redis session storage is partially configured.")

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        raise EscalationSessionStoreError("Redis session storage is partially configured.")

    async def delete(self, handoff_id: str) -> None:
        raise EscalationSessionStoreError("Redis session storage is partially configured.")


class UpstashRedisEscalationSessionStore:
    def __init__(
        self,
        *,
        rest_url: str,
        rest_token: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._rest_url = rest_url.rstrip("/")
        self._rest_token = rest_token
        self._timeout_seconds = timeout_seconds

    async def create(
        self,
        escalation_request: EscalationRequest,
        *,
        ttl_seconds: int,
    ) -> EscalationSessionRecord:
        if ttl_seconds <= 0:
            raise EscalationSessionStoreError("Escalation session TTL must be positive.")

        handoff_id = _create_handoff_id()
        created_at = datetime.now(UTC).replace(microsecond=0)
        expires_at = created_at + timedelta(seconds=ttl_seconds)
        record = EscalationSessionRecord(
            handoff_id=handoff_id,
            state=ESCALATION_SESSION_STATE_WAITING_FOR_ALEX,
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
            transcript=[
                {"role": item.role, "content": item.content}
                for item in escalation_request.transcript
            ],
        )

        result = await self._execute(
            ["SET", _session_key(handoff_id), _to_json(record), "EX", ttl_seconds]
        )
        if result != "OK":
            raise EscalationSessionStoreError("Redis did not confirm session storage.")

        return record

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        result = await self._execute(["GET", _session_key(handoff_id)])
        if result is None:
            return None
        if not isinstance(result, str):
            raise EscalationSessionStoreError("Stored escalation session is not valid JSON text.")

        try:
            payload = json.loads(result)
        except json.JSONDecodeError as exc:
            raise EscalationSessionStoreError("Stored escalation session is invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise EscalationSessionStoreError("Stored escalation session payload is invalid.")

        return EscalationSessionRecord.from_dict(payload)

    async def delete(self, handoff_id: str) -> None:
        await self._execute(["DEL", _session_key(handoff_id)])

    async def _execute(self, command: list[Any]) -> Any:
        return await run_in_threadpool(self._execute_sync, command)

    def _execute_sync(self, command: list[Any]) -> Any:
        payload = json.dumps(command, separators=(",", ":")).encode("utf-8")
        request = Request(
            self._rest_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._rest_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError) as exc:
            raise EscalationSessionStoreError("Redis REST request failed.") from exc

        try:
            decoded_response = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise EscalationSessionStoreError("Redis REST response was not valid JSON.") from exc

        if not isinstance(decoded_response, dict):
            raise EscalationSessionStoreError("Redis REST response had an unexpected shape.")

        if "error" in decoded_response:
            raise EscalationSessionStoreError("Redis REST command failed.")

        return decoded_response.get("result")


def _create_handoff_id() -> str:
    return f"hnd_{uuid.uuid4().hex}"


def _session_key(handoff_id: str) -> str:
    return f"{ESCALATION_SESSION_KEY_PREFIX}{handoff_id}"


def _to_json(record: EscalationSessionRecord) -> str:
    return json.dumps(record.to_dict(), ensure_ascii=False, separators=(",", ":"))
