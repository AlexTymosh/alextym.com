from app.core.config import Settings
from app.rag.readiness import RagReadinessProbeProtocol
from app.schemas.health import LiveResponse, ReadyResponse, WarmupResponse


class HealthService:
    def __init__(
        self,
        settings: Settings,
        rag_readiness_probe: RagReadinessProbeProtocol | None = None,
    ) -> None:
        self._settings = settings
        self._rag_readiness_probe = rag_readiness_probe

    def live(self) -> LiveResponse:
        return LiveResponse(status="alive")

    def ready(self) -> ReadyResponse:
        vector_db_status = self._vector_db_status()
        return ReadyResponse(
            status="not_ready" if vector_db_status == "not_ready" else "ready",
            app="ready",
            environment=self._settings.environment,
            vector_db=vector_db_status,
            llm_config=self._configured_status(self._settings.openai_api_key),
            contact_email=self._configured_status(
                self._settings.resend_api_key,
                self._settings.contact_target_email,
                self._settings.contact_from_email,
            ),
        )

    def _vector_db_status(self) -> str:
        if not self._settings.qdrant_url or not self._settings.qdrant_api_key:
            return "not_configured"
        if self._rag_readiness_probe is None:
            return "not_ready"
        return self._rag_readiness_probe.check().status

    def warmup(self) -> WarmupResponse:
        return WarmupResponse(
            status="warmed",
            app="ready",
            environment=self._settings.environment,
        )

    @staticmethod
    def _configured_status(*values: str) -> str:
        return "configured" if all(values) else "not_configured"
