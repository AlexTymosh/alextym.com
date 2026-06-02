from app.rag.models import ChunkMetadata, KnowledgeChunk, RetrievalFilter
from app.rag.qdrant_retriever import QdrantRetriever


def test_qdrant_retriever_adds_route_hints_to_embedding_query() -> None:
    embedding_client = FakeEmbeddingClient()
    search_store = FakeSearchStore([])
    retriever = QdrantRetriever(
        embedding_client=embedding_client,
        store=search_store,
        default_limit=6,
        score_threshold=0.5,
    )

    retriever.retrieve("What are Alex's soft skills?")

    assert embedding_client.last_text is not None
    assert "soft-skills-working-style" in embedding_client.last_text
    assert "working-style" in embedding_client.last_text


def test_qdrant_retriever_passes_route_payload_filter_to_store() -> None:
    search_store = FakeSearchStore([])
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=search_store,
        default_limit=6,
        score_threshold=0.5,
    )

    retriever.retrieve("Can Alex provide a share code?")

    assert search_store.last_payload_filter is not None
    assert search_store.last_payload_filter.topic_any == ("right-to-work-uk-location",)
    assert "share-code" in search_store.last_payload_filter.tag_any


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
        self.last_payload_filter: RetrievalFilter | None = None

    def search(
        self,
        *,
        embedding: list[float],
        limit: int,
        score_threshold: float,
        payload_filter: RetrievalFilter | None = None,
    ) -> list[KnowledgeChunk]:
        self.last_payload_filter = payload_filter
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
