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
    assert resolution.standalone_question == question
    assert resolution.resolution_method == "rules"
    assert resolution.requires_retrieval is False


def test_llm_resolution_records_model_method_and_standalone_question() -> None:
    question = "Tell me about his work experience"
    request = ChatRequest(
        message=question,
        history=[{"role": "assistant", "content": "Ask about Alex's profile."}],
    )
    llm_client = StaticIntentLLMClient(
        '{"intent":"alex_profile_question","rewritten_query":'
        '"Tell me about Alex work experience","confidence":"high",'
        '"reason":"his refers to Alex from context"}'
    )

    resolution = resolve_question(request, llm_client=llm_client)

    assert resolution.intent == "alex_profile_question"
    assert resolution.original_question == question
    assert resolution.standalone_question == "Tell me about Alex work experience"
    assert resolution.resolution_method == "llm"
    assert resolution.requires_retrieval is True


class StaticIntentLLMClient:
    def __init__(self, answer: str) -> None:
        self._answer = answer

    def answer(self, prompt: object) -> str:
        return self._answer
