import re
from collections.abc import Iterable

from app.rag.models import KnowledgeChunk
from app.rag.query_router import QueryRoute

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", re.IGNORECASE)

STOP_WORDS = {
    "a",
    "alex",
    "an",
    "and",
    "are",
    "as",
    "about",
    "can",
    "does",
    "for",
    "from",
    "has",
    "have",
    "he",
    "her",
    "his",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "profile",
    "skill",
    "skills",
    "summary",
    "tell",
    "the",
    "to",
    "use",
    "used",
    "uses",
    "using",
    "what",
    "when",
    "where",
    "who",
    "with",
    "work",
    "worked",
    "works",
}


def build_keyword_terms(query: str, *, route: QueryRoute) -> frozenset[str]:
    raw_terms = [query]
    if route.intent != "general_profile":
        raw_terms.extend(
            [
                " ".join(route.topic_hints),
                " ".join(route.tag_hints),
                " ".join(route.section_hints),
            ]
        )

    return frozenset(_tokenize(" ".join(raw_terms)))


def keyword_score_chunk(
    chunk: KnowledgeChunk,
    *,
    query_terms: Iterable[str],
) -> float:
    normalized_query_terms = set(query_terms)
    if not normalized_query_terms:
        return 0.0

    chunk_terms = set(_tokenize(_chunk_text(chunk)))
    matched_terms = normalized_query_terms.intersection(chunk_terms)

    if not matched_terms:
        return 0.0

    return min(1.5, 0.35 * len(matched_terms))


def _chunk_text(chunk: KnowledgeChunk) -> str:
    extra = chunk.metadata.extra
    fields = [
        chunk.metadata.source,
        chunk.metadata.section,
        chunk.metadata.topic,
        " ".join(chunk.metadata.tags),
        chunk.content,
        " ".join(_string_list(extra.get("answer_facts"))),
        " ".join(_string_list(extra.get("retrieval_hints"))),
        _vector_keywords(extra.get("vector_inputs")),
    ]
    return " ".join(field for field in fields if field)


def _vector_keywords(value: object) -> str:
    if not isinstance(value, dict):
        return ""

    keywords = value.get("keywords_sparse")
    return keywords if isinstance(keywords, str) else ""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, str) and item]


def _tokenize(value: str) -> list[str]:
    tokens: list[str] = []
    for raw_token in TOKEN_PATTERN.findall(value.casefold()):
        normalized_token = _normalize_token(raw_token)
        if not normalized_token or normalized_token in STOP_WORDS:
            continue

        tokens.append(normalized_token)
        if "-" in normalized_token or "_" in normalized_token:
            tokens.extend(
                part
                for part in re.split(r"[-_]+", normalized_token)
                if part and part not in STOP_WORDS
            )

    return tokens


def _normalize_token(value: str) -> str:
    token = value.strip("-_")
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token
