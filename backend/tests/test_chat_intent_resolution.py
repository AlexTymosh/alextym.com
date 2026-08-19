from app.schemas.chat import ChatRequest
from app.services.chat_intent_resolution import QuestionResolution, resolve_question


def test_rule_resolution_exposes_explicit_question_model() -> None:
    question = "What are Alex's main strengths?"

    resolution = resolve_question(ChatRequest(message=question), llm_client=None)

    assert resolution == QuestionResolution(
        intent="alex_profile_question",
        original_question=question,
        standalone_question=(
            "Tell me about Alex's professional strengths, working style, "
            "automation-first thinking, and collaboration approach."
        ),
        conversational_context="",
        resolution_method="rules",
    )
    assert resolution.requires_retrieval is True


def test_rule_resolution_distinguishes_third_party_question() -> None:
    question = "Who is Elon Musk?"

    resolution = resolve_question(ChatRequest(message=question), llm_client=None)

    assert resolution.intent == "third_party_question"
    assert resolution.original_question == question
    assert resolution.standalone_question is None
    assert resolution.resolution_method == "rules"
    assert resolution.requires_retrieval is False


def test_llm_resolution_records_model_method_and_standalone_question() -> None:
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
    llm_client = StaticIntentLLMClient(
        '{"intent":"alex_profile_question","standalone_question":'
        '"Tell me about Alex work experience","confidence":"high",'
        '"reason":"his refers to Alex from context"}'
    )

    resolution = resolve_question(request, llm_client=llm_client)

    assert resolution.intent == "alex_profile_question"
    assert resolution.original_question == question
    assert resolution.standalone_question == "Tell me about Alex work experience"
    assert resolution.resolution_method == "llm"
    assert resolution.requires_retrieval is True


def test_llm_resolution_contextualizes_short_confirmation() -> None:
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
    llm_client = StaticIntentLLMClient(
        '{"intent":"alex_profile_question","standalone_question":'
        '"Give an example from Alex work experience that demonstrates his strengths",'
        '"confidence":"high","reason":"yes accepts the preceding offer"}'
    )

    resolution = resolve_question(request, llm_client=llm_client)

    assert resolution.original_question == question
    assert resolution.standalone_question == (
        "Give an example from Alex work experience that demonstrates his strengths"
    )
    assert resolution.resolution_method == "llm"
    assert "Would you like to see an example from his experience?" in (
        resolution.conversational_context
    )


def test_invalid_llm_resolution_falls_back_to_clarification() -> None:
    request = ChatRequest(
        message="yes",
        history=[
            {"role": "assistant", "content": "Would you like more about Alex?"},
        ],
    )
    llm_client = StaticIntentLLMClient(
        '{"intent":"alex_profile_question","confidence":"high",'
        '"reason":"missing standalone question"}'
    )

    resolution = resolve_question(request, llm_client=llm_client)

    assert resolution.intent == "clarification_required"
    assert resolution.standalone_question is None
    assert resolution.resolution_method == "fallback"


def test_direct_question_does_not_call_contextualizer() -> None:
    resolution = resolve_question(
        ChatRequest(message="What are Alex's main strengths?"),
        llm_client=UnexpectedLLMClient(),
    )

    assert resolution.intent == "alex_profile_question"
    assert resolution.resolution_method == "rules"


def test_explicit_pronoun_follow_up_uses_rules_before_contextualizer() -> None:
    resolution = resolve_question(
        ChatRequest(
            message="Tell me about his work experience",
            history=[{"role": "assistant", "content": "Ask about Alex's profile."}],
        ),
        llm_client=UnexpectedLLMClient(),
    )

    assert resolution.standalone_question == "Tell me about Alex's work experience."
    assert resolution.resolution_method == "rules"


class StaticIntentLLMClient:
    def __init__(self, answer: str) -> None:
        self._answer = answer

    def answer(self, prompt: object) -> str:
        return self._answer


class UnexpectedLLMClient:
    def answer(self, prompt: object) -> str:
        raise AssertionError("Direct questions must not call the contextualizer.")
