from app.schemas.chat import ChatHistoryMessage
from app.services.chat_intent_resolution import format_conversation_context


def test_conversation_context_preserves_valid_history_message() -> None:
    content = ("Alex " + "builds reliable automation systems. " * 40).strip()
    history = [ChatHistoryMessage(role="assistant", content=content)]

    context = format_conversation_context(history)

    assert len(content) > 500
    assert context == f"assistant: {content}"
