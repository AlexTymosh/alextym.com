from app.schemas.chat import ChatHistoryMessage
from app.services.chat_intent_resolution import format_conversation_context


def test_conversation_context_preserves_valid_history_message() -> None:
    content = ("Alex " + "builds reliable automation systems. " * 40).strip()
    history = [ChatHistoryMessage(role="assistant", content=content)]

    context = format_conversation_context(history)

    assert len(content) > 500
    assert context == f"assistant: {content}"


def test_conversation_context_preserves_owner_identity_and_message_order() -> None:
    history = [
        ChatHistoryMessage(role="user", content="Which project should I read about?"),
        ChatHistoryMessage(role="owner", content="I suggest my portfolio website.\nAny questions?"),
        ChatHistoryMessage(role="assistant", content="The live chat has ended."),
    ]

    assert format_conversation_context(history) == (
        "user: Which project should I read about?\n"
        "owner: I suggest my portfolio website. Any questions?\n"
        "assistant: The live chat has ended."
    )
