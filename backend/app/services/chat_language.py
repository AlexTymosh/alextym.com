import re
from typing import Literal

LanguageStatus = Literal["russian", "ukrainian", "other"]

NON_ENGLISH_LATIN_MARKERS = (
    "ayudar",
    "bonjour",
    "ciao",
    "czy",
    "danke",
    "dziekuje",
    "guten",
    "hola",
    "kann",
    "merci",
    "moze",
    "pouvez",
    "puede",
    "puoi",
    "strone",
    "vous",
)

ENGLISH_LANGUAGE_ANCHORS = (
    "ask",
    "build",
    "can",
    "could",
    "does",
    "experience",
    "help",
    "how",
    "is",
    "need",
    "project",
    "tell",
    "website",
    "what",
    "with",
    "work",
    "would",
)

UKRAINIAN_SPECIFIC_CYRILLIC_CHARS = frozenset("\u0404\u0406\u0407\u0490\u0454\u0456\u0457\u0491")
UKRAINIAN_LANGUAGE_MARKERS = (
    "\u0431\u0443\u0434\u044c \u043b\u0430\u0441\u043a\u0430",
    "\u043c\u0435\u043d\u0456",
    "\u043c\u043e\u0436\u0435\u0448",
    "\u043e\u043b\u0435\u043a\u0441",
    "\u043f\u0440\u0438\u0432\u0456\u0442",
    "\u0440\u043e\u0437\u043a\u0430\u0436\u0438",
    "\u0443\u043a\u0440\u0430\u0457\u043d",
    "\u0445\u043e\u0447\u0443 \u0437\u0432'\u044f\u0437\u0430\u0442\u0438\u0441\u044f",
)
RUSSIAN_LANGUAGE_MARKERS = (
    "\u043f\u0440\u0438\u0432\u0435\u0442",
    "\u0440\u0430\u0441\u0441\u043a\u0430\u0436\u0438",
    "\u0441\u0432\u044f\u0437\u0430\u0442\u044c\u0441\u044f",
    "\u0445\u043e\u0447\u0443 \u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u044c",
)


def normalize_message(message: str) -> str:
    return " ".join(message.casefold().strip(" \t\r\n.,!?;:`'\"\u2026").split())


def detect_unsupported_language(message: str) -> LanguageStatus | None:
    cleaned_message = _strip_noise_for_language_detection(message)
    normalized_message = normalize_message(cleaned_message)

    if _looks_like_non_english_latin(normalized_message):
        return "other"

    letters = [character for character in cleaned_message if character.isalpha()]
    if not letters:
        return None

    latin_count = sum(1 for character in letters if _is_latin_ascii(character))
    cyrillic_count = sum(1 for character in letters if _is_cyrillic(character))
    other_count = len(letters) - latin_count - cyrillic_count
    total_letters = len(letters)

    cyrillic_ratio = cyrillic_count / total_letters
    other_ratio = other_count / total_letters

    if cyrillic_count >= 4 and cyrillic_ratio >= 0.45:
        return _classify_cyrillic_language(cleaned_message, normalized_message)
    if cyrillic_count >= 12 and cyrillic_ratio >= 0.25:
        return _classify_cyrillic_language(cleaned_message, normalized_message)
    if other_count >= 6 and other_ratio >= 0.35:
        return "other"
    if other_count >= 12 and other_ratio >= 0.25:
        return "other"

    return None


def _classify_cyrillic_language(
    message: str,
    normalized_message: str,
) -> LanguageStatus:
    if any(character in UKRAINIAN_SPECIFIC_CYRILLIC_CHARS for character in message):
        return "ukrainian"
    if any(marker in normalized_message for marker in UKRAINIAN_LANGUAGE_MARKERS):
        return "ukrainian"
    if any(marker in normalized_message for marker in RUSSIAN_LANGUAGE_MARKERS):
        return "russian"
    return "russian"


def _strip_noise_for_language_detection(message: str) -> str:
    without_code_blocks = re.sub(r"```.*?```", " ", message, flags=re.DOTALL)
    without_inline_code = re.sub(r"`[^`]*`", " ", without_code_blocks)
    without_urls = re.sub(r"https?://\S+|www\.\S+", " ", without_inline_code)
    return re.sub(r"\S+@\S+", " ", without_urls)


def _is_latin_ascii(character: str) -> bool:
    folded_character = character.casefold()
    return "a" <= folded_character <= "z"


def _is_cyrillic(character: str) -> bool:
    return "\u0400" <= character <= "\u04ff"


def _looks_like_non_english_latin(normalized_message: str) -> bool:
    tokens = set(normalized_message.split())
    if not tokens:
        return False

    marker_count = len(tokens.intersection(NON_ENGLISH_LATIN_MARKERS))
    english_anchor_count = len(tokens.intersection(ENGLISH_LANGUAGE_ANCHORS))
    return marker_count >= 2 and english_anchor_count < 2
