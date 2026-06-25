from app.core.project_config import get_project_config

_PROJECT_CONFIG = get_project_config()
OWNER_REFERENCE = _PROJECT_CONFIG.assistant.owner_reference

ALEX_TERMS = tuple(
    dict.fromkeys(
        [
            OWNER_REFERENCE.casefold(),
            *(alias.casefold() for alias in _PROJECT_CONFIG.owner.public_aliases),
        ]
    )
)

GREETING_PATTERNS = (
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "how are you",
    "how do you do",
)

HELP_PATTERNS = (
    "help",
    "what can you do",
    "what can i ask",
    "how can you help",
)

ASSISTANT_INTRO_PATTERNS = (
    "introduce yourself",
    "who are you",
    "what are you",
    "tell me about yourself",
)

SOCIAL_ACKNOWLEDGEMENT_PATTERNS = (
    "cool",
    "nice",
    "great",
    "thanks",
    "thank you",
    "many thanks",
    "ok",
    "okay",
    "got it",
    "understood",
    "sounds good",
)

PRIVATE_DATA_PATTERNS = (
    "private phone",
    "phone number",
    "personal email",
    "private email",
    "home address",
    "private address",
)
PRIVATE_DATA_ALEX_TERMS = (*ALEX_TERMS, "his", "him", "you", "your")
