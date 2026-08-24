from app.llm.openai_client import OpenAIResponsesClient
from app.services.question_contextualizer import (
    ContextualizedQuestion,
    build_question_contextualization_prompt,
)


class OpenAIQuestionContextualizer:
    def __init__(self, responses_client: OpenAIResponsesClient) -> None:
        self._responses_client = responses_client

    def contextualize(
        self,
        *,
        message: str,
        conversational_context: str,
    ) -> ContextualizedQuestion:
        prompt = build_question_contextualization_prompt(
            message=message,
            conversational_context=conversational_context,
        )
        return self._responses_client.parse_structured(prompt, ContextualizedQuestion)
