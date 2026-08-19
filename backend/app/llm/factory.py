from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.llm.client import LLMClient
from app.llm.openai_client import OpenAIResponsesClient
from app.llm.openai_question_contextualizer import OpenAIQuestionContextualizer
from app.services.question_contextualizer import QuestionContextualizer


@dataclass(frozen=True)
class ConfiguredLLMClients:
    answer: LLMClient
    question_contextualizer: QuestionContextualizer


def get_configured_llm_clients(
    settings: Settings | None = None,
) -> ConfiguredLLMClients | None:
    resolved_settings = settings or get_settings()
    if not resolved_settings.openai_api_key:
        return None

    responses_client = OpenAIResponsesClient.from_settings(resolved_settings)
    return ConfiguredLLMClients(
        answer=responses_client,
        question_contextualizer=OpenAIQuestionContextualizer(responses_client),
    )
