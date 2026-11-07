import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from starlette.concurrency import run_in_threadpool

from app.repositories.escalation_session_store import EscalationSessionStoreError
from app.domain.escalation_session import (
    EscalationSessionRecord,
    build_append_alex_message_transition,
    build_close_session_transition,
)

ESCALATION_SESSION_KEY_PREFIX = "escalation:session:"

# Redis EVAL is one atomic server operation. Python domain rules remain the
# only source of truth; Lua only checks that the read snapshot is still current.
ATOMIC_CAS_SCRIPT = """local current = redis.call('GET', KEYS[1])
if not current or current ~= ARGV[1] then
    return 0
end
if ARGV[2] == 'delete' then
    redis.call('DEL', KEYS[1])
elseif ARGV[2] == 'set' then
    redis.call('SET', KEYS[1], ARGV[3], 'EX', tonumber(ARGV[4]))
else
    return redis.error_reply('invalid escalation CAS operation')
end
return 1
"""
MAX_CAS_ATTEMPTS = 8


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
        snapshot = await self._read_snapshot(handoff_id)
        return snapshot[1] if snapshot is not None else None

    async def append_alex_message(
        self,
        handoff_id: str,
        content: str,
    ) -> EscalationSessionRecord | None:
        for _ in range(MAX_CAS_ATTEMPTS):
            snapshot = await self._read_snapshot(handoff_id)
            if snapshot is None:
                return None
            original, record = snapshot
            try:
                transition = build_append_alex_message_transition(record, content)
            except ValueError as exc:
                raise EscalationSessionStoreError("Stored session expiry is invalid.") from exc
            if transition.should_delete:
                if await self._compare_and_swap(handoff_id, original, None, None):
                    return None
                continue
            if transition.record is None:
                return None
            ttl = _required_ttl(transition.ttl_seconds)
            if await self._compare_and_swap(handoff_id, original, transition.record, ttl):
                return transition.record

        raise EscalationSessionStoreError("Too many concurrent session updates.")

    async def close(
        self,
        handoff_id: str,
        *,
        close_message: str | None = None,
    ) -> EscalationSessionRecord | None:
        for _ in range(MAX_CAS_ATTEMPTS):
            snapshot = await self._read_snapshot(handoff_id)
            if snapshot is None:
                return None
            original, record = snapshot
            try:
                transition = build_close_session_transition(record, close_message=close_message)
            except ValueError as exc:
                raise EscalationSessionStoreError("Stored session expiry is invalid.") from exc
            if transition.should_delete:
                if await self._compare_and_swap(handoff_id, original, None, None):
                    return None
                continue
            if transition.record is None:
                return None
            if transition.ttl_seconds is None:
                return transition.record  # Existing idempotent closed-session behaviour.
            if await self._compare_and_swap(
                handoff_id, original, transition.record, transition.ttl_seconds
            ):
                return transition.record

        raise EscalationSessionStoreError("Too many concurrent session updates.")

    async def delete(self, handoff_id: str) -> None:
        result = await self._execute(["DEL", _session_key(handoff_id)])
        # Redis DEL returns 0 for absent keys and 1 for a removed key.
        # Only a confirmed integer reply is sufficient for HTTP 204.
        if type(result) is not int or result not in (0, 1):
            raise EscalationSessionStoreError("Redis did not confirm session deletion.")

    async def _read_snapshot(self, handoff_id: str) -> tuple[str, EscalationSessionRecord] | None:
        raw = await self._execute(["GET", _session_key(handoff_id)])
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise EscalationSessionStoreError("Stored escalation session is not valid JSON.")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EscalationSessionStoreError("Stored session is invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise EscalationSessionStoreError("Stored escalation session payload is invalid.")
        return raw, EscalationSessionRecord.from_dict(payload)

    async def _compare_and_swap(
        self,
        handoff_id: str,
        expected_json: str,
        updated_record: EscalationSessionRecord | None,
        ttl_seconds: int | None,
    ) -> bool:
        command: list[Any] = [
            "EVAL",
            ATOMIC_CAS_SCRIPT,
            "1",
            _session_key(handoff_id),
            expected_json,
        ]
        if updated_record is None:
            command.append("delete")
        else:
            command.extend(["set", _to_json(updated_record), _required_ttl(ttl_seconds)])
        result = await self._execute(command)
        if type(result) is not int or result not in (0, 1):
            raise EscalationSessionStoreError("Redis CAS returned an unexpected result.")
        return result == 1

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
