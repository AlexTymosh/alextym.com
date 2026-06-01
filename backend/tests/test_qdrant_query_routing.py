from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.qdrant_retriever import QdrantRetriever


def test_qdrant_retriever_adds_route_hints_to_embedding_query() -> None:
    embedding_client = FakeEmbeddingClient()
    retriever = QdrantRetriever(
        embedding_client=embedding_client,
        store=FakeSearchStore([]),
        default_limit=6,
        score_threshold=0.5,
    )

    retriever.retrieve("What are Alex's soft skills?")

    assert embedding_client.last_text is not None
    assert "soft-skills-working-style" in embedding_client.last_text
    assert "working-style" in embedding_client.last_text


def test_qdrant_retriever_preserves_existing_keyword_expansions() -> None:
    embedding_client = FakeEmbeddingClient()
    retriever = QdrantRetriever(
        embedding_client=embedding_client,
        store=FakeSearchStore([]),
        default_limit=6,
        score_threshold=0.5,
    )

    retriever.retrieve("Does Alex have SQL experience?")

    assert embedding_client.last_text is not None
    assert "PostgreSQL SQLAlchemy Alembic" in embedding_client.last_text


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.last_text: str | None = None

    def embed_text(self, text: str) -> list[float]:
        self.last_text = text
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
    ) -> list[KnowledgeChunk]:
        return self.chunks[:limit]


def _chunk(chunk_id: str, topic: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        content="content",
        metadata=ChunkMetadata(
            source="source",
            section="experience",
            topic=topic,
        ),
    )
