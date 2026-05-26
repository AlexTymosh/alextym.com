from app.core.config import Settings
from app.schemas.health import LiveResponse, ReadyResponse, WarmupResponse


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def live(self) -> LiveResponse:
        return LiveResponse(status="alive")

    def ready(self) -> ReadyResponse:
        return ReadyResponse(
            status="ready",
            app="ready",
            environment=self._settings.environment,
            vector_db=self._configured_status(
                self._settings.qdrant_url, self._settings.qdrant_api_key
            ),
            llm_config=self._configured_status(self._settings.openai_api_key),
            contact_email=self._configured_status(
                self._settings.resend_api_key,
                self._settings.contact_target_email,
                self._settings.contact_from_email,
            ),
        )

    def warmup(self) -> WarmupResponse:
        return WarmupResponse(
            status="warmed",
            app="ready",
            environment=self._settings.environment,
        )

    @staticmethod
    def _configured_status(*values: str) -> str:
        return "configured" if all(values) else "not_configured"
