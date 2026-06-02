from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.qdrant_retriever import QdrantRetriever


def test_reranker_promotes_topic_match_over_raw_dense_order() -> None:
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=FakeSearchStore(
            [
                _chunk(
                    "general",
                    topic="summary",
                    tags=("summary",),
                    score=0.95,
                ),
                _chunk(
                    "soft-skills",
                    topic="soft-skills-working-style",
                    tags=("soft-skills", "working-style"),
                    score=0.65,
                ),
            ]
        ),
        default_limit=6,
        score_threshold=0.5,
    )

    chunks = retriever.retrieve("What are Alex's soft skills?")

    assert [chunk.id for chunk in chunks] == ["soft-skills", "general"]


def test_reranker_keeps_dense_order_when_route_does_not_match() -> None:
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=FakeSearchStore(
            [
                _chunk("first", topic="summary", tags=("summary",), score=0.9),
                _chunk("second", topic="experience", tags=("api",), score=0.8),
            ]
        ),
        default_limit=6,
        score_threshold=0.5,
    )

    chunks = retriever.retrieve("Tell me about Alex.")

    assert [chunk.id for chunk in chunks] == ["first", "second"]


def test_reranker_uses_tag_match_when_topic_is_not_exact() -> None:
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=FakeSearchStore(
            [
                _chunk("generic", topic="summary", tags=("summary",), score=0.8),
                _chunk("skills", topic="tools", tags=("hard-skills",), score=0.5),
            ]
        ),
        default_limit=6,
        score_threshold=0.5,
    )

    chunks = retriever.retrieve("What are Alex's hard skills?")

    assert [chunk.id for chunk in chunks] == ["skills", "generic"]


class FakeEmbeddingClient:
    def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeSearchStore:
    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self.chunks = chunks

    def search(
        self,
        *,
        embedding: list[float],
        limit: int,
        score_threshold: float,
        payload_filter=None,
    ) -> list[KnowledgeChunk]:
        return self.chunks[:limit]


def _chunk(
    chunk_id: str,
    *,
    topic: str,
    tags: tuple[str, ...],
    score: float,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        content="content",
        metadata=ChunkMetadata(
            source="source",
            section="experience",
            topic=topic,
            tags=tags,
            extra={"retrieval_score": score},
        ),
    )
