from types import SimpleNamespace

import pytest

from app.llm.client import ProviderRequestError
from app.llm.openai_client import OpenAIResponsesClient
from app.llm.openai_question_contextualizer import OpenAIQuestionContextualizer
from app.services.question_contextualizer import ContextualizedQuestion


def test_openai_contextualizer_enforces_contextualized_question_schema() -> None:
    expected = ContextualizedQuestion(
        intent="alex_profile_question",
        standalone_question="Give an example from Alex's experience",
        confidence="high",
        reason="yes accepts the immediately preceding offer",
    )
    responses = FakeStructuredResponses(output_parsed=expected)
    contextualizer = _contextualizer(responses)

    resolution = contextualizer.contextualize(
        message="yes",
        conversational_context=(
            "assistant: Alex uses systems thinking. Would you like an example?"
        ),
    )

    assert resolution is expected
    assert responses.last_request["text_format"] is ContextualizedQuestion
    assert responses.last_request["model"] == "gpt-5-mini"
    assert responses.last_request["max_output_tokens"] == 300
    assert responses.last_request["reasoning"] == {"effort": "low"}
    assert responses.last_request["input"][-1] == {"role": "user", "content": "yes"}
    confidence_schema = ContextualizedQuestion.model_json_schema()["properties"]["confidence"]
    assert confidence_schema["enum"] == ["low", "medium", "high"]


def test_openai_contextualizer_rejects_missing_parsed_output() -> None:
    contextualizer = _contextualizer(FakeStructuredResponses(output_parsed=None))

    with pytest.raises(ProviderRequestError, match="structured output"):
        contextualizer.contextualize(
            message="yes",
            conversational_context="assistant: Would you like an example?",
        )


def test_openai_contextualizer_maps_provider_failure() -> None:
    contextualizer = _contextualizer(FakeStructuredResponses(error=RuntimeError("failed")))

    with pytest.raises(ProviderRequestError, match="structured response request failed"):
        contextualizer.contextualize(
            message="yes",
            conversational_context="assistant: Would you like an example?",
        )


def _contextualizer(responses: "FakeStructuredResponses") -> OpenAIQuestionContextualizer:
    responses_client = OpenAIResponsesClient(
        api_key="",
        model="gpt-5-mini",
        max_output_tokens=300,
        reasoning_effort="low",
        client=SimpleNamespace(responses=responses),
    )
    return OpenAIQuestionContextualizer(responses_client)


class FakeStructuredResponses:
    def __init__(
        self,
        *,
        output_parsed: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self._output_parsed = output_parsed
        self._error = error
        self.last_request: dict[str, object] = {}

    def parse(self, **kwargs: object) -> SimpleNamespace:
        self.last_request = dict(kwargs)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(output_parsed=self._output_parsed)
