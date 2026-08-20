from app.llm.client import ProviderRequestError
from app.schemas.chat import ChatRequest
from app.services.chat_intent_resolution import (
    QuestionResolution,
    is_weakness_request,
    resolve_question,
)
from app.services.question_contextualizer import ContextualizedQuestion


def test_rule_resolution_exposes_explicit_question_model() -> None:
    question = "What are Alex's main strengths?"

    resolution = resolve_question(
        ChatRequest(message=question),
        question_contextualizer=None,
    )

    assert resolution == QuestionResolution(
        intent="alex_profile_question",
        original_question=question,
        standalone_question=question,
        conversational_context="",
        resolution_method="rules",
    )
    assert resolution.requires_retrieval is True


def test_rule_resolution_distinguishes_third_party_question() -> None:
    question = "Who is Elon Musk?"

    resolution = resolve_question(
        ChatRequest(message=question),
        question_contextualizer=None,
    )

    assert resolution.intent == "third_party_question"
    assert resolution.original_question == question
    assert resolution.standalone_question is None
    assert resolution.resolution_method == "rules"
    assert resolution.requires_retrieval is False


def test_contextualizer_resolution_records_model_method_and_standalone_question() -> None:
    question = "What about him?"
    request = ChatRequest(
        message=question,
        history=[
            {
                "role": "assistant",
                "content": "Alex has UK work experience. Would you like more detail?",
            }
        ],
    )
    contextualizer = StaticQuestionContextualizer(
        ContextualizedQuestion(
            intent="alex_profile_question",
            standalone_question="Tell me about Alex work experience",
            confidence="high",
            reason="him refers to Alex from context",
        )
    )

    resolution = resolve_question(request, question_contextualizer=contextualizer)

    assert resolution.intent == "alex_profile_question"
    assert resolution.original_question == question
    assert resolution.standalone_question == "Tell me about Alex work experience"
    assert resolution.resolution_method == "llm"
    assert resolution.requires_retrieval is True


def test_contextualizer_resolves_frontend_scripted_confirmation() -> None:
    question = "yes"
    request = ChatRequest(
        message=question,
        history=[
            {"role": "user", "content": "What are Alex's main strengths?"},
            {
                "role": "assistant",
                "content": (
                    "Alex's main strengths include systems thinking. "
                    "Would you like to see an example from his experience?"
                ),
            },
        ],
    )
    contextualizer = StaticQuestionContextualizer(
        ContextualizedQuestion(
            intent="alex_profile_question",
            standalone_question=(
                "Give an example from Alex work experience that demonstrates his strengths"
            ),
            confidence="high",
            reason="yes accepts the preceding offer",
        )
    )

    resolution = resolve_question(request, question_contextualizer=contextualizer)

    assert resolution.original_question == question
    assert resolution.standalone_question == (
        "Give an example from Alex work experience that demonstrates his strengths"
    )
    assert resolution.resolution_method == "llm"
    assert contextualizer.last_message == "yes"
    assert "Would you like to see an example from his experience?" in contextualizer.last_context


def test_low_confidence_contextualization_requests_clarification() -> None:
    request = ChatRequest(
        message="yes",
        history=[
            {"role": "assistant", "content": "Would you like more about Alex?"},
        ],
    )
    contextualizer = StaticQuestionContextualizer(
        ContextualizedQuestion(
            intent="alex_profile_question",
            standalone_question="Tell me more about Alex",
            confidence="low",
            reason="The offer does not identify a specific topic",
        )
    )

    resolution = resolve_question(request, question_contextualizer=contextualizer)

    assert resolution.intent == "clarification_required"
    assert resolution.standalone_question is None
    assert resolution.resolution_method == "llm"


def test_contextualizer_provider_failure_falls_back_to_clarification() -> None:
    request = ChatRequest(
        message="yes",
        history=[
            {"role": "assistant", "content": "Would you like more about Alex?"},
        ],
    )

    resolution = resolve_question(
        request,
        question_contextualizer=FailingQuestionContextualizer(),
    )

    assert resolution.intent == "clarification_required"
    assert resolution.standalone_question is None
    assert resolution.resolution_method == "fallback"


def test_direct_question_does_not_call_contextualizer() -> None:
    resolution = resolve_question(
        ChatRequest(message="What are Alex's main strengths?"),
        question_contextualizer=UnexpectedQuestionContextualizer(),
    )

    assert resolution.intent == "alex_profile_question"
    assert resolution.resolution_method == "rules"


def test_explicit_pronoun_follow_up_uses_rules_before_contextualizer() -> None:
    resolution = resolve_question(
        ChatRequest(
            message="Tell me about his work experience",
            history=[{"role": "assistant", "content": "Ask about Alex's profile."}],
        ),
        question_contextualizer=UnexpectedQuestionContextualizer(),
    )

    assert resolution.standalone_question == "Tell me about Alex's work experience"
    assert resolution.resolution_method == "rules"


def test_weakness_policy_distinguishes_personal_and_case_limitations() -> None:
    assert is_weakness_request("What are Alex's professional limitations?", []) is True
    assert is_weakness_request("What are your weaknesses?", []) is True
    assert (
        is_weakness_request(
            "What limitations applied to the site owner's corporate credit-risk analysis?",
            [],
        )
        is False
    )


class StaticQuestionContextualizer:
    def __init__(self, resolution: ContextualizedQuestion) -> None:
        self._resolution = resolution
        self.last_message = ""
        self.last_context = ""

    def contextualize(
        self,
        *,
        message: str,
        conversational_context: str,
    ) -> ContextualizedQuestion:
        self.last_message = message
        self.last_context = conversational_context
        return self._resolution


class FailingQuestionContextualizer:
    def contextualize(
        self,
        *,
        message: str,
        conversational_context: str,
    ) -> ContextualizedQuestion:
        raise ProviderRequestError("Provider failed.")


class UnexpectedQuestionContextualizer:
    def contextualize(
        self,
        *,
        message: str,
        conversational_context: str,
    ) -> ContextualizedQuestion:
        raise AssertionError("Direct questions must not call the contextualizer.")
