from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.qdrant_retriever import QdrantRetriever


def test_hybrid_keyword_score_promotes_exact_term_match() -> None:
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=FakeSearchStore(
            [
                _chunk(
                    "summary",
                    content="Alex works with Python APIs.",
                    topic="summary",
                    tags=("python",),
                    score=0.9,
                ),
                _chunk(
                    "bitrix",
                    content="Alex worked with Bitrix24 CRM integration flows.",
                    topic="business-systems",
                    tags=("crm", "bitrix24"),
                    score=0.75,
                ),
            ]
        ),
        default_limit=6,
        score_threshold=0.5,
    )

    chunks = retriever.retrieve("Does Alex use Bitrix24 integrations?")

    assert [chunk.id for chunk in chunks] == ["bitrix", "summary"]


def test_hybrid_keyword_score_keeps_topic_match_dominant() -> None:
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=FakeSearchStore(
            [
                _chunk(
                    "keyword-only",
                    content="Soft skills are mentioned here.",
                    topic="summary",
                    tags=("summary",),
                    score=0.95,
                ),
                _chunk(
                    "soft-skills",
                    content="Alex communicates clearly.",
                    topic="soft-skills-working-style",
                    tags=("soft-skills", "working-style"),
                    score=0.6,
                ),
            ]
        ),
        default_limit=6,
        score_threshold=0.5,
    )

    chunks = retriever.retrieve("What are Alex's soft skills?")

    assert [chunk.id for chunk in chunks] == ["soft-skills", "keyword-only"]


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
    content: str,
    topic: str,
    tags: tuple[str, ...],
    score: float,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        content=content,
        metadata=ChunkMetadata(
            source="source",
            section="experience",
            topic=topic,
            tags=tags,
            extra={"retrieval_score": score},
        ),
    )
