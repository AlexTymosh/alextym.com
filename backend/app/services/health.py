import os

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
            vector_db=self._configured_status("QDRANT_URL", "QDRANT_API_KEY"),
            llm_config=self._configured_status("OPENAI_API_KEY"),
            contact_email=self._configured_status("CONTACT_TARGET_EMAIL"),
        )

    def warmup(self) -> WarmupResponse:
        return WarmupResponse(
            status="warmed",
            app="ready",
            environment=self._settings.environment,
        )

    @staticmethod
    def _configured_status(*env_names: str) -> str:
        return "configured" if all(os.getenv(name) for name in env_names) else "not_configured"
