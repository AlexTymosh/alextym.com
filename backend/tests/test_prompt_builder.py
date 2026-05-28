from app.rag.prompt_builder import GENERAL_CHAT_SYSTEM_INSTRUCTIONS, SYSTEM_INSTRUCTIONS


def test_system_prompts_describe_handoff_without_claiming_completion() -> None:
    for instructions in (SYSTEM_INSTRUCTIONS, GENERAL_CHAT_SYSTEM_INSTRUCTIONS):
        assert "handoff after explicit user confirmation" in instructions
        assert "Do not say that Alex has already been notified" in instructions
        assert "Do not ask for a phone number or email address" in instructions
