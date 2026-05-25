from app.core.config import Settings, get_settings
from app.llm.client import LLMClient
from app.llm.openai_client import OpenAIResponsesClient


def get_configured_llm_client(settings: Settings | None = None) -> LLMClient | None:
    resolved_settings = settings or get_settings()
    if not resolved_settings.openai_api_key:
        return None
    return OpenAIResponsesClient.from_settings(resolved_settings)
