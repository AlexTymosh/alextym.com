from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
from app.llm.openai_client import OpenAIEmbeddingClient, OpenAIResponsesClient
from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.qdrant_store import QdrantKnowledgeStore
from scripts.ingest_knowledge import ingest_public_knowledge


def test_openai_embedding_client_embeds_texts_with_configured_dimensions() -> None:
    fake_embeddings = FakeOpenAIEmbeddings()
    client = OpenAIEmbeddingClient(
        api_key="",
        model="text-embedding-3-small",
        dimensions=2,
        client=SimpleNamespace(embeddings=fake_embeddings),
    )

    embeddings = client.embed_texts(["first", "second"])

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]
    assert fake_embeddings.last_request == {
        "model": "text-embedding-3-small",
        "input": ["first", "second"],
        "dimensions": 2,
    }


def test_openai_responses_client_returns_output_text() -> None:
    fake_responses = FakeOpenAIResponses()
    client = OpenAIResponsesClient(
        api_key="",
        model="gpt-5-mini",
        max_output_tokens=300,
        client=SimpleNamespace(responses=fake_responses),
    )

    answer = client.answer(
        SimpleNamespace(
            as_messages=lambda: [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "context"},
                {"role": "user", "content": "question"},
            ]
        )
    )

    assert answer == "Grounded answer."
    assert fake_responses.last_request["model"] == "gpt-5-mini"
    assert fake_responses.last_request["max_output_tokens"] == 300


def test_qdrant_store_replaces_source_chunks() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge",
        client=fake_qdrant,
    )
    chunk = _chunk("chunk-1", "Alex builds FastAPI services.")

    store.replace_source_chunks(
        chunks=[chunk],
        embeddings=[[0.1, 0.2]],
        source_files=("resume.md",),
        vector_size=2,
    )

    assert fake_qdrant.operations == ["collection_exists", "create_collection", "delete", "upsert"]
    assert fake_qdrant.upserted_points[0].payload["chunk_id"] == "chunk-1"
    assert fake_qdrant.upserted_points[0].payload["source"] == "resume.md"


def test_qdrant_store_search_maps_payload_to_chunks() -> None:
    fake_qdrant = FakeQdrantClient(
        search_points=[
            SimpleNamespace(
                id="point-1",
                payload={
                    "chunk_id": "chunk-1",
                    "content": "Alex builds FastAPI services.",
                    "source": "resume.md",
                    "section": "Summary",
                    "topic": "summary",
                    "visibility": "public",
                    "confidence": "self-reported",
                    "source_confidence": "medium",
                    "tags": ["backend"],
                },
            )
        ]
    )
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge",
        client=fake_qdrant,
    )

    chunks = store.search(embedding=[0.1, 0.2], limit=1, score_threshold=0.72)

    assert len(chunks) == 1
    assert chunks[0].id == "chunk-1"
    assert chunks[0].metadata.source == "resume.md"
    assert chunks[0].metadata.tags == ("backend",)


def test_ingestion_replaces_vectors_from_reviewed_public_knowledge() -> None:
    knowledge_dir = _local_knowledge_dir("provider-ingestion")
    (knowledge_dir / "resume.md").write_text(
        "# Resume\n\n## Summary\n\nAlex builds FastAPI services.",
        encoding="utf-8",
    )
    fake_embedding_client = FakeEmbeddingClient()
    fake_vector_store = FakeVectorStore()

    summary = ingest_public_knowledge(
        settings=_settings(),
        knowledge_dir=knowledge_dir,
        embedding_client=fake_embedding_client,
        vector_store=fake_vector_store,
    )

    assert summary.loaded_chunks == 1
    assert summary.indexed_chunks == 1
    assert fake_embedding_client.texts == ["Alex builds FastAPI services."]
    assert fake_vector_store.replaced_chunks[0].metadata.source == "resume.md"
    assert fake_vector_store.source_files == ("resume.md",)


def test_ingestion_cleans_sources_when_public_knowledge_is_empty() -> None:
    knowledge_dir = _local_knowledge_dir("provider-empty-ingestion")
    (knowledge_dir / "resume.md").write_text(
        "# Resume\n\n<!-- alextym:placeholder -->\n\nPlaceholder.",
        encoding="utf-8",
    )
    fake_embedding_client = FakeEmbeddingClient()
    fake_vector_store = FakeVectorStore()

    summary = ingest_public_knowledge(
        settings=_settings(),
        knowledge_dir=knowledge_dir,
        embedding_client=fake_embedding_client,
        vector_store=fake_vector_store,
    )

    assert summary.loaded_chunks == 0
    assert summary.indexed_chunks == 0
    assert fake_embedding_client.texts == []
    assert fake_vector_store.replaced_chunks == []
    assert fake_vector_store.source_files == ("resume.md",)


class FakeOpenAIEmbeddings:
    def __init__(self) -> None:
        self.last_request: dict[str, object] | None = None

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.last_request = dict(kwargs)
        return SimpleNamespace(
            data=[
                SimpleNamespace(embedding=[1.0, 0.0]),
                SimpleNamespace(embedding=[0.0, 1.0]),
            ]
        )


class FakeOpenAIResponses:
    def __init__(self) -> None:
        self.last_request: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.last_request = dict(kwargs)
        return SimpleNamespace(output_text="Grounded answer.")


class FakeQdrantClient:
    def __init__(self, search_points: list[SimpleNamespace] | None = None) -> None:
        self.operations: list[str] = []
        self.upserted_points: list[object] = []
        self._search_points = search_points or []

    def collection_exists(self, *, collection_name: str) -> bool:
        self.operations.append("collection_exists")
        return False

    def create_collection(self, **kwargs: object) -> None:
        self.operations.append("create_collection")

    def delete(self, **kwargs: object) -> None:
        self.operations.append("delete")

    def upsert(self, *, collection_name: str, points: list[object]) -> None:
        self.operations.append("upsert")
        self.upserted_points = points

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(points=self._search_points)


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.texts = texts
        return [[1.0, 0.0] for _ in texts]

    def embed_text(self, text: str) -> list[float]:
        return [1.0, 0.0] if text else []


class FakeVectorStore:
    def __init__(self) -> None:
        self.replaced_chunks: list[KnowledgeChunk] = []
        self.replaced_embeddings: list[list[float]] = []
        self.source_files: tuple[str, ...] = ()
        self.vector_size = 0

    def replace_source_chunks(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        source_files: tuple[str, ...],
        vector_size: int,
    ) -> None:
        self.replaced_chunks = chunks
        self.replaced_embeddings = embeddings
        self.source_files = source_files
        self.vector_size = vector_size


def _chunk(chunk_id: str, content: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        content=content,
        metadata=ChunkMetadata(source="resume.md", section="Summary", topic="summary"),
    )


def _settings() -> Settings:
    return Settings(
        app_name="alextym API",
        environment="test",
        frontend_origin="http://localhost:3000",
        openai_api_key="test-key",
        openai_model="gpt-5-mini",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_dimensions=2,
        openai_max_output_tokens=300,
        qdrant_url="http://qdrant.test",
        qdrant_api_key="",
        qdrant_collection="alex_public_knowledge",
        rag_top_k=6,
        rag_score_threshold=0.72,
        rate_limiting_enabled=True,
        chat_daily_limit_per_ip=50,
    )


def _local_knowledge_dir(name: str) -> Path:
    test_root = Path.cwd() / ".tmp" / "test-rag-providers" / name
    if test_root.exists():
        for file_path in test_root.iterdir():
            file_path.unlink()
    test_root.mkdir(parents=True, exist_ok=True)
    return test_root
