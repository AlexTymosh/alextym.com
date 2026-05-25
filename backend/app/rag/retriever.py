import re
from collections.abc import Iterable
from typing import Protocol

from app.rag.models import KnowledgeChunk

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "about",
    "alex",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "his",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "tell",
    "that",
    "the",
    "this",
    "to",
    "what",
    "with",
    "you",
    "your",
}


class Retriever(Protocol):
    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeChunk]:
        """Return public knowledge chunks relevant to the query."""


class EmptyRetriever:
    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeChunk]:
        return []


class InMemoryRetriever:
    def __init__(self, chunks: Iterable[KnowledgeChunk]) -> None:
        self._chunks = list(chunks)

    def retrieve(self, query: str, *, limit: int = 6) -> list[KnowledgeChunk]:
        query_terms = _tokenize(query)
        if not query_terms:
            return []

        scored_chunks = [
            (self._score_chunk(query_terms, chunk), chunk)
            for chunk in self._chunks
            if chunk.metadata.visibility == "public"
        ]
        matching_chunks = [(score, chunk) for score, chunk in scored_chunks if score > 0]
        matching_chunks.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in matching_chunks[:limit]]

    @staticmethod
    def _score_chunk(query_terms: set[str], chunk: KnowledgeChunk) -> int:
        chunk_terms = _tokenize(
            " ".join(
                [
                    chunk.metadata.source,
                    chunk.metadata.section,
                    chunk.metadata.topic,
                    chunk.content,
                ]
            )
        )
        return len(query_terms.intersection(chunk_terms))


def _tokenize(text: str) -> set[str]:
    return {token for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOP_WORDS}
