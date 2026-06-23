import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from starlette.concurrency import run_in_threadpool

from app.repositories.escalation_session_store import EscalationSessionStoreError
from app.services.escalation_session_state import (
    EscalationSessionRecord,
    build_append_alex_message_transition,
    build_close_session_transition,
)

ESCALATION_SESSION_KEY_PREFIX = "escalation:session:"


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
        session_record: EscalationSessionRecord,
        *,
        ttl_seconds: int,
    ) -> EscalationSessionRecord:
        if ttl_seconds <= 0:
            raise EscalationSessionStoreError("Escalation session TTL must be positive.")

        result = await self._execute(
            [
                "SET",
                _session_key(session_record.handoff_id),
                _to_json(session_record),
                "EX",
                ttl_seconds,
            ]
        )
        if result != "OK":
            raise EscalationSessionStoreError("Redis did not confirm session storage.")

        return session_record

    async def get(self, handoff_id: str) -> EscalationSessionRecord | None:
        result = await self._execute(["GET", _session_key(handoff_id)])
        if result is None:
            return None
        if not isinstance(result, str):
            raise EscalationSessionStoreError("Stored escalation session is not valid JSON.")

        try:
            payload = json.loads(result)
        except json.JSONDecodeError as exc:
            raise EscalationSessionStoreError("Stored session is invalid JSON.") from exc

        if not isinstance(payload, dict):
            raise EscalationSessionStoreError("Stored escalation session payload is invalid.")

        return EscalationSessionRecord.from_dict(payload)

    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        record = await self.get(handoff_id)
        if record is None:
            return None

        try:
            transition = build_append_alex_message_transition(record, content)
        except ValueError as exc:
            raise EscalationSessionStoreError("Stored session expiry is invalid.") from exc
        if transition.should_delete:
            await self.delete(handoff_id)
        if transition.record is None:
            return None

        await self._save(transition.record, ttl_seconds=_required_ttl(transition.ttl_seconds))
        return transition.record

    async def close(
        self,
        handoff_id: str,
        *,
        close_message: str | None = None,
    ) -> EscalationSessionRecord | None:
        record = await self.get(handoff_id)
        if record is None:
            return None

        try:
            transition = build_close_session_transition(record, close_message=close_message)
        except ValueError as exc:
            raise EscalationSessionStoreError("Stored session expiry is invalid.") from exc
        if transition.should_delete:
            await self.delete(handoff_id)
        if transition.record is None:
            return None
        if transition.ttl_seconds is None:
            return transition.record

        await self._save(transition.record, ttl_seconds=transition.ttl_seconds)
        return transition.record

    async def delete(self, handoff_id: str) -> None:
        await self._execute(["DEL", _session_key(handoff_id)])

    async def _save(
        self,
        record: EscalationSessionRecord,
        *,
        ttl_seconds: int,
    ) -> None:
        result = await self._execute(
            [
                "SET",
                _session_key(record.handoff_id),
                _to_json(record),
                "EX",
                ttl_seconds,
            ]
        )
        if result != "OK":
            raise EscalationSessionStoreError("Redis did not confirm session update.")

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


def _session_key(handoff_id: str) -> str:
    return f"{ESCALATION_SESSION_KEY_PREFIX}{handoff_id}"


def _to_json(record: EscalationSessionRecord) -> str:
    return json.dumps(record.to_dict(), ensure_ascii=False, separators=(",", ":"))


def _required_ttl(ttl_seconds: int | None) -> int:
    if ttl_seconds is None:
        raise EscalationSessionStoreError("Session transition did not include a TTL.")
    return ttl_seconds
