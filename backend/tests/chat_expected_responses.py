"""Expected public chat responses used by endpoint regression tests.

These literals intentionally duplicate the public response contract instead of
importing production constants from app.services.chat or app.services.chat_policy.
That keeps the tests decoupled from the implementation module split while still
protecting user-facing answer text from accidental drift.
"""

INSUFFICIENT_DATA_ANSWER = (
    "I do not have enough reliable information in the public knowledge base "
    "to answer that accurately. \n"
    "Would you like me to connect you with Alex?"
)

GREETING_ANSWER = "Hi. I\u2019m Alex's digital assistant. How can I help you today?"

ASSISTANT_INTRO_ANSWER = (
    "I\u2019m Alex's digital assistant. \nI can tell you about Alex's professional background."
)

UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER = (
    "\u0418\u0437\u0432\u0438\u043d\u0438\u0442\u0435, \u0410\u043b\u0435\u043a\u0441\u0435\u0439 \u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0438\u043b \u043c\u0435\u043d\u044f \u0432 \u043e\u0431\u0449\u0435\u043d\u0438\u0438 \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c \u044f\u0437\u044b\u043a\u0435. "
    "\u042f \u043c\u043e\u0433\u0443 \u043e\u0442\u0432\u0435\u0447\u0430\u0442\u044c \u0442\u043e\u043b\u044c\u043a\u043e \u043f\u043e-\u0430\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u0438.\n"
    "\u0414\u043b\u044f \u043e\u0431\u0449\u0435\u043d\u0438\u044f \u043f\u043e-\u0440\u0443\u0441\u0441\u043a\u0438 \u044f \u043c\u043e\u0433\u0443 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0438\u0442\u044c \u043f\u0440\u044f\u043c\u043e\u0435 \u043e\u0431\u0449\u0435\u043d\u0438\u0435."
)

UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER = (
    "\u0412\u0438\u0431\u0430\u0447\u0442\u0435, \u041e\u043b\u0435\u043a\u0441\u0456\u0439 \u043e\u0431\u043c\u0435\u0436\u0438\u0432 \u043c\u0435\u043d\u0435 \u0443 \u0441\u043f\u0456\u043b\u043a\u0443\u0432\u0430\u043d\u043d\u0456 \u0443\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u043e\u044e \u043c\u043e\u0432\u043e\u044e. "
    "\u042f \u043c\u043e\u0436\u0443 \u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0434\u0430\u0442\u0438 \u043b\u0438\u0448\u0435 \u0430\u043d\u0433\u043b\u0456\u0439\u0441\u044c\u043a\u043e\u044e.\n"
    "\u042f\u043a\u0449\u043e \u0432\u0430\u043c \u0437\u0440\u0443\u0447\u043d\u0456\u0448\u0435 \u0441\u043f\u0456\u043b\u043a\u0443\u0432\u0430\u0442\u0438\u0441\u044f \u0440\u0456\u0434\u043d\u043e\u044e \u043c\u043e\u0432\u043e\u044e, "
    "\u044f \u043c\u043e\u0436\u0443 \u0437\u0430\u043f\u0440\u043e\u043f\u043e\u043d\u0443\u0432\u0430\u0442\u0438 \u043f\u0440\u044f\u043c\u0435 \u0437\u0432\u0435\u0440\u043d\u0435\u043d\u043d\u044f."
)

UNSUPPORTED_NON_ENGLISH_ANSWER = (
    "Sorry, Alex has limited me to English.\n"
    "Please ask your question in English, or use the contact option below "
    "to reach Alex directly."
)
