READING_QUICK_REPLY = (
    "Hi, I\u2019m connected now and reading your request. Please give me a moment."
)
CONTACT_QUICK_REPLY = (
    "Hi, I\u2019m connected now, but I\u2019m sorry, I\u2019m short on time at the moment. "
    "Is your question urgent, or can we continue in 20\u201330 minutes?"
)
STILL_THERE_QUICK_REPLY = "Are you still there? I\u2019m ready to continue when you are."

READING_QUICK_REPLY_BUTTON_LABEL = (
    "\U0001f44b Send: \u201cHi, I\u2019m connected now and reading...\u201d"
)
CONTACT_QUICK_REPLY_BUTTON_LABEL = (
    "\u23f3 Send: \u201cHi, I\u2019m connected, but I\u2019m sorry...\u201d"
)
STILL_THERE_QUICK_REPLY_BUTTON_LABEL = (
    "\u2753 Send: \u201cAre you still there? I\u2019m ready...\u201d"
)

HANDOFF_CLOSED_AFTER_NO_RESPONSE_REPLY = (
    "This conversation has been closed because there was no response for a while. "
    "You can request a new connection with the site owner if needed."
)

_QUICK_REPLIES_BY_CALLBACK_ACTION = {
    "reading": READING_QUICK_REPLY,
    "contact": CONTACT_QUICK_REPLY,
    "still": STILL_THERE_QUICK_REPLY,
}


def quick_reply_for_callback_action(action: str) -> str | None:
    return _QUICK_REPLIES_BY_CALLBACK_ACTION.get(action)
