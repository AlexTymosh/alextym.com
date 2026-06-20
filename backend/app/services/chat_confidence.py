import re

from app.rag.models import KnowledgeChunk
from app.schemas.chat import Confidence


def confidence_from_chunks(chunks: list[KnowledgeChunk], query: str) -> Confidence:
    if not chunks:
        return "low"

    scores = sorted(
        (score for chunk in chunks if (score := _retrieval_score(chunk)) is not None),
        reverse=True,
    )
    top_score = scores[0] if scores else None
    score_gap = scores[0] - scores[1] if len(scores) > 1 else 0.0
    source_rank = max(_source_confidence_rank(chunk) for chunk in chunks)
    answer_fact_count = sum(_answer_fact_count(chunk) for chunk in chunks[:3])
    exact_match = _has_exact_metadata_match(query, chunks[:3])

    if top_score is None:
        if exact_match and source_rank >= 2:
            return "high"
        if answer_fact_count >= 2 or source_rank >= 2:
            return "medium"
        return "low"

    if top_score >= 0.78 and (score_gap >= 0.05 or exact_match):
        return "high"
    if top_score >= 0.72 and answer_fact_count >= 2 and source_rank >= 2:
        return "high"
    if top_score >= 0.55 or exact_match or answer_fact_count >= 2:
        return "medium"
    return "low"


def _retrieval_score(chunk: KnowledgeChunk) -> float | None:
    value = chunk.metadata.extra.get("retrieval_score")
    return float(value) if isinstance(value, (int, float)) else None


def _source_confidence_rank(chunk: KnowledgeChunk) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(
        chunk.metadata.source_confidence,
        2,
    )


def _answer_fact_count(chunk: KnowledgeChunk) -> int:
    value = chunk.metadata.extra.get("answer_facts")
    if not isinstance(value, list):
        return 0
    return sum(1 for item in value if isinstance(item, str) and item.strip())


def _has_exact_metadata_match(query: str, chunks: list[KnowledgeChunk]) -> bool:
    query_terms = _confidence_terms(query)
    if not query_terms:
        return False

    for chunk in chunks:
        metadata_terms = _confidence_terms(
            " ".join(
                [
                    chunk.metadata.section,
                    chunk.metadata.topic,
                    " ".join(chunk.metadata.tags),
                ]
            )
        )
        if query_terms.intersection(metadata_terms):
            return True
    return False


def _confidence_terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9]+", value.casefold()) if len(term) > 3}
