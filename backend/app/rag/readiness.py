from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from time import monotonic
from typing import Literal, Protocol

import structlog

from app.core.config import Settings
from app.rag.collection_contract import RagCollectionContract
from app.rag.errors import RetrievalError
from app.rag.qdrant_store import QdrantKnowledgeStore

logger = structlog.get_logger(__name__)

RagReadinessStatus = Literal["ready", "not_ready"]
DEFAULT_READINESS_CACHE_SECONDS = 60.0


@dataclass(frozen=True)
class RagReadinessResult:
    status: RagReadinessStatus
    error_code: str | None = None


class RagReadinessProbeProtocol(Protocol):
    def check(self) -> RagReadinessResult: ...


class RagReadinessProbe:
    def __init__(
        self,
        checker: Callable[[], None],
        *,
        ttl_seconds: float = DEFAULT_READINESS_CACHE_SECONDS,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._checker = checker
        self._ttl_seconds = max(0.0, ttl_seconds)
        self._clock = clock
        self._lock = Lock()
        self._cached_result: RagReadinessResult | None = None
        self._checked_at: float | None = None

    def check(self) -> RagReadinessResult:
        now = self._clock()
        with self._lock:
            if self._is_cache_current(now):
                return self._cached_result or RagReadinessResult(status="not_ready")

            result = self._run_check()
            self._cached_result = result
            self._checked_at = now
            return result

    def _is_cache_current(self, now: float) -> bool:
        return (
            self._cached_result is not None
            and self._checked_at is not None
            and now - self._checked_at < self._ttl_seconds
        )

    def _run_check(self) -> RagReadinessResult:
        try:
            self._checker()
        except RetrievalError as exc:
            logger.warning(
                "rag.readiness.failed",
                message="RAG readiness contract check failed.",
                retrieval_stage=exc.stage,
                error_code=exc.code,
                error_type=type(exc).__name__,
                retryable=exc.retryable,
            )
            return RagReadinessResult(status="not_ready", error_code=exc.code)
        except Exception as exc:
            logger.exception(
                "rag.readiness.failed",
                message="Unexpected RAG readiness check failure.",
                retrieval_stage="collection_contract",
                error_code="unexpected_error",
                error_type=type(exc).__name__,
                retryable=True,
            )
            return RagReadinessResult(
                status="not_ready",
                error_code="unexpected_error",
            )
        return RagReadinessResult(status="ready")


@lru_cache
def get_rag_readiness_probe(
    settings: Settings,
) -> RagReadinessProbeProtocol | None:
    if not settings.qdrant_url or not settings.qdrant_api_key:
        return None

    store = QdrantKnowledgeStore.from_settings(settings)

    def check_contract() -> None:
        store.validate_contract(RagCollectionContract.for_runtime(settings))

    return RagReadinessProbe(check_contract)
