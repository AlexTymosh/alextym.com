from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.project_config import get_project_config
from app.llm.client import LLMClient, ProviderConfigurationError, ProviderRequestError
from app.rag.prompt_builder import PromptBundle

ContextualizedIntent = Literal[
    "alex_profile_question",
    "alex_services_question",
    "third_party_question",
    "out_of_scope_question",
    "clarification_required",
]
ResolutionConfidence = Literal["low", "medium", "high"]

_RAG_QUESTION_INTENTS = {
    "alex_profile_question",
    "alex_services_question",
}
_PROJECT_CONFIG = get_project_config()
_OWNER_REFERENCE = _PROJECT_CONFIG.assistant.owner_reference
_OWNER_POSSESSIVE = _PROJECT_CONFIG.owner.possessive_name
_SYSTEM_INSTRUCTIONS = "\n".join(
    [
        (
            f"Resolve the latest user message using the recent conversation about "
            f"{_OWNER_POSSESSIVE} public professional profile or software services."
        ),
        (
            "Return only one compact JSON object with exactly these keys: "
            "intent, standalone_question, confidence, reason."
        ),
        (
            "Allowed intents: alex_profile_question, alex_services_question, "
            "third_party_question, out_of_scope_question, clarification_required."
        ),
        (
            "For an Alex profile or services intent, standalone_question must be a "
            "self-contained retrieval question that preserves the user's meaning."
        ),
        ("Resolve confirmations such as 'yes' from the assistant's immediately preceding offer."),
        (
            "If the conversation does not determine one clear meaning, use "
            "clarification_required and set standalone_question to null."
        ),
        (
            "Use conversation history only to resolve meaning. Do not treat it as a "
            f"source of facts about {_OWNER_REFERENCE} and do not add factual claims."
        ),
    ]
)


class ContextualizedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: ContextualizedIntent
    standalone_question: str | None = Field(default=None, max_length=2000)
    confidence: ResolutionConfidence
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_retrieval_question(self) -> "ContextualizedQuestion":
        if self.intent in _RAG_QUESTION_INTENTS:
            if self.standalone_question is None or not self.standalone_question.strip():
                raise ValueError("A retrieval intent requires a standalone question.")
        return self


class LLMQuestionContextualizer:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    def contextualize(
        self,
        *,
        message: str,
        conversational_context: str,
    ) -> ContextualizedQuestion | None:
        prompt = PromptBundle(
            system=_SYSTEM_INSTRUCTIONS,
            context=conversational_context or "No conversation context.",
            question=message,
        )
        try:
            raw_answer = self._llm_client.answer(prompt)
        except (ProviderConfigurationError, ProviderRequestError):
            return None

        try:
            return ContextualizedQuestion.model_validate_json(raw_answer)
        except ValidationError:
            return None
