from app.core.project_config import get_project_config

_PROJECT_CONFIG = get_project_config()
OWNER_REFERENCE = _PROJECT_CONFIG.assistant.owner_reference
OWNER_POSSESSIVE = _PROJECT_CONFIG.owner.possessive_name
_OWNER_RUSSIAN_NAME = _PROJECT_CONFIG.owner.russian_name
_OWNER_UKRAINIAN_NAME = _PROJECT_CONFIG.owner.ukrainian_name

HANDOFF_PROMPT_TITLE = f"Would you like to connect with {OWNER_REFERENCE}?"

INSUFFICIENT_DATA_ANSWER = (
    "I do not have enough reliable information in the public knowledge base "
    "to answer that accurately. \n"
    f"Would you like me to connect you with {OWNER_REFERENCE}?"
)
PROMPT_INJECTION_ANSWER = (
    "I\u2019m not sure I can help with that request.\n"
    f"Let\u2019s focus on {OWNER_POSSESSIVE} professional background or "
    "collaboration options. \n"
    "Could you clarify what you\u2019d like to know?"
)
UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER = (
    "\u0418\u0437\u0432\u0438\u043d\u0438\u0442\u0435, "
    f"{_OWNER_RUSSIAN_NAME} "
    "\u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0438\u043b "
    "\u043c\u0435\u043d\u044f \u0432 \u043e\u0431\u0449\u0435\u043d\u0438\u0438 "
    "\u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c "
    "\u044f\u0437\u044b\u043a\u0435. \u042f \u043c\u043e\u0433\u0443 "
    "\u043e\u0442\u0432\u0435\u0447\u0430\u0442\u044c "
    "\u0442\u043e\u043b\u044c\u043a\u043e "
    "\u043f\u043e-\u0430\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u0438.\n"
    "\u0414\u043b\u044f \u043e\u0431\u0449\u0435\u043d\u0438\u044f "
    "\u043f\u043e-\u0440\u0443\u0441\u0441\u043a\u0438 \u044f "
    "\u043c\u043e\u0433\u0443 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0438\u0442\u044c "
    "\u043f\u0440\u044f\u043c\u043e\u0435 \u043e\u0431\u0449\u0435\u043d\u0438\u0435."
)
UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER = (
    "\u0412\u0438\u0431\u0430\u0447\u0442\u0435, "
    f"{_OWNER_UKRAINIAN_NAME} "
    "\u043e\u0431\u043c\u0435\u0436\u0438\u0432 \u043c\u0435\u043d\u0435 "
    "\u0443 \u0441\u043f\u0456\u043b\u043a\u0443\u0432\u0430\u043d\u043d\u0456 "
    "\u0443\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u043e\u044e "
    "\u043c\u043e\u0432\u043e\u044e. \u042f \u043c\u043e\u0436\u0443 "
    "\u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0434\u0430\u0442\u0438 "
    "\u043b\u0438\u0448\u0435 "
    "\u0430\u043d\u0433\u043b\u0456\u0439\u0441\u044c\u043a\u043e\u044e.\n"
    "\u042f\u043a\u0449\u043e \u0432\u0430\u043c \u0437\u0440\u0443\u0447\u043d\u0456\u0448\u0435 "
    "\u0441\u043f\u0456\u043b\u043a\u0443\u0432\u0430\u0442\u0438\u0441\u044f "
    "\u0440\u0456\u0434\u043d\u043e\u044e \u043c\u043e\u0432\u043e\u044e, "
    "\u044f \u043c\u043e\u0436\u0443 "
    "\u0437\u0430\u043f\u0440\u043e\u043f\u043e\u043d\u0443\u0432\u0430\u0442\u0438 "
    "\u043f\u0440\u044f\u043c\u0435 \u0437\u0432\u0435\u0440\u043d\u0435\u043d\u043d\u044f."
)
UNSUPPORTED_NON_ENGLISH_ANSWER = (
    f"Sorry, {OWNER_REFERENCE} has limited me to English.\n"
    "Please ask your question in English, or use the contact option below "
    f"to reach {OWNER_REFERENCE} directly."
)
OUT_OF_SCOPE_ANSWER = (
    "To help you best, could you clarify your request?\n"
    f"I handle professional enquiries about {OWNER_POSSESSIVE} expertise "
    "and background.\n"
    f"You can also type 'connect me with {OWNER_REFERENCE}' to reach "
    "them directly."
)
HANDOFF_REQUEST_ANSWER = (
    f"I can connect you with {OWNER_REFERENCE} directly. Please confirm below to continue."
)
PUBLIC_BOUNDARY_WEAKNESSES_ANSWER = (
    "Thank you for the deeper interest.\n"
    f"{OWNER_REFERENCE} prefers to discuss their weaknesses directly rather "
    "than through a public assistant.\n"
    "I can share verified information about their professional background, "
    f"or you can type \u201cconnect me with {OWNER_REFERENCE}\u201d so I can "
    "connect you with them for a direct conversation.\n"
)
SOCIAL_ACKNOWLEDGEMENT_ANSWER = "OK. How else can I help?"
PRIVATE_DATA_ANSWER = PROMPT_INJECTION_ANSWER
GREETING_ANSWER = f"Hi. I\u2019m {OWNER_POSSESSIVE} digital assistant. How can I help you today?"
HELP_ANSWER = (
    f"You can ask about {OWNER_POSSESSIVE} experience, projects, software "
    "services, availability, or contact options."
)
ASSISTANT_INTRO_ANSWER = (
    f"I\u2019m {OWNER_POSSESSIVE} digital assistant. \n"
    f"I can tell you about {OWNER_POSSESSIVE} professional background."
)
LANGUAGE_FALLBACK_ANSWERS = {
    "russian": UNSUPPORTED_RUSSIAN_LANGUAGE_ANSWER,
    "ukrainian": UNSUPPORTED_UKRAINIAN_LANGUAGE_ANSWER,
    "other": UNSUPPORTED_NON_ENGLISH_ANSWER,
}
