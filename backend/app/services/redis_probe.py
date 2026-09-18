import asyncio
from uuid import uuid4

import httpx


REDIS_PROBE_TIMEOUT_SECONDS = 15.0
REDIS_PROBE_TTL_SECONDS = 60


class RedisProbeError(Exception):
    """A bounded error category that is safe to log without provider details."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RedisProbeService:
    def __init__(
        self,
        rest_url: str,
        rest_token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._rest_url = rest_url
        self._rest_token = rest_token
        self._transport = transport

    async def check(self) -> None:
        self._validate_configuration()
        deadline = asyncio.get_running_loop().time() + REDIS_PROBE_TIMEOUT_SECONDS
        key = f"system:probe:redis:{uuid4().hex}"
        value = uuid4().hex
        failure: RedisProbeError | None = None

        async with httpx.AsyncClient(
            timeout=5.0,
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            try:
                result = await self._execute(
                    client, ["SET", key, value, "EX", REDIS_PROBE_TTL_SECONDS], deadline
                )
                if result != "OK":
                    raise RedisProbeError("write_failed")
                if await self._execute(client, ["GET", key], deadline) != value:
                    raise RedisProbeError("value_mismatch")
            except RedisProbeError as exc:
                failure = exc
            finally:
                # Cleanup shares the deadline. The TTL handles an unavailable Redis
                # or a write that succeeded remotely before a response was lost.
                try:
                    deleted = await self._execute(client, ["DEL", key], deadline)
                    if type(deleted) is not int or deleted != 1:
                        raise RedisProbeError("cleanup_failed")
                except RedisProbeError as exc:
                    if failure is None:
                        failure = exc

        if failure is not None:
            raise failure

    def _validate_configuration(self) -> None:
        if not self._rest_url or not self._rest_token:
            raise RedisProbeError("configuration")
        try:
            url = httpx.URL(self._rest_url)
        except httpx.InvalidURL:
            raise RedisProbeError("configuration") from None
        if (
            url.scheme != "https"
            or not url.host
            or "%" in url.host
            or url.userinfo
            or url.query
            or url.fragment
        ):
            raise RedisProbeError("configuration")

    async def _execute(
        self,
        client: httpx.AsyncClient,
        command: list[str | int],
        deadline: float,
    ) -> object:
        if asyncio.get_running_loop().time() >= deadline:
            raise RedisProbeError("timeout")
        try:
            async with asyncio.timeout_at(deadline):
                response = await client.post(
                    self._rest_url,
                    headers={"Authorization": f"Bearer {self._rest_token}"},
                    json=command,
                )
                response.raise_for_status()
                payload = response.json()
        except (TimeoutError, httpx.TimeoutException):
            raise RedisProbeError("timeout") from None
        except httpx.HTTPStatusError:
            raise RedisProbeError("http_status") from None
        except httpx.HTTPError:
            raise RedisProbeError("connection") from None
        except ValueError:
            raise RedisProbeError("invalid_response") from None

        if not isinstance(payload, dict) or "error" in payload or "result" not in payload:
            raise RedisProbeError("invalid_response")
        return payload["result"]
