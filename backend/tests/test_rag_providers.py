from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
from app.llm.openai_client import OpenAIEmbeddingClient, OpenAIResponsesClient
from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.qdrant_retriever import QdrantRetriever
from app.rag.qdrant_store import QdrantKnowledgeStore
from scripts.ingest_knowledge import ingest_public_knowledge

EXPECTED_QDRANT_INDEX_FIELDS = [
    ("source", "keyword"),
    ("source_file", "keyword"),
    ("section", "keyword"),
    ("topic", "keyword"),
    ("visibility", "keyword"),
    ("tags", "keyword"),
]


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
        reasoning_effort="low",
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
    assert fake_responses.last_request["reasoning"] == {"effort": "low"}


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

    assert fake_qdrant.operations == [
        "collection_exists",
        "create_collection",
        "create_payload_index",
        "create_payload_index",
        "create_payload_index",
        "create_payload_index",
        "create_payload_index",
        "create_payload_index",
        "delete",
        "delete",
        "upsert",
    ]
    assert fake_qdrant.indexed_fields == EXPECTED_QDRANT_INDEX_FIELDS
    assert fake_qdrant.deleted_filters == [
        ("source_file", "resume.md"),
        ("source", "resume.md"),
    ]
    assert fake_qdrant.upserted_points[0].payload["chunk_id"] == "chunk-1"
    assert fake_qdrant.upserted_points[0].payload["source"] == "resume.md"


def test_qdrant_store_ensures_payload_indexes_for_existing_collection() -> None:
    fake_qdrant = FakeQdrantClient(collection_exists=True)
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge",
        client=fake_qdrant,
    )

    store.ensure_collection(vector_size=2)

    assert fake_qdrant.operations == [
        "collection_exists",
        "create_payload_index",
        "create_payload_index",
        "create_payload_index",
        "create_payload_index",
        "create_payload_index",
        "create_payload_index",
    ]
    assert fake_qdrant.indexed_fields == EXPECTED_QDRANT_INDEX_FIELDS


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


def test_qdrant_retriever_filters_link_sections_for_professional_queries() -> None:
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=FakeSearchStore(
            [
                _chunk("links", "GitHub profile.", section="Links"),
                _chunk(
                    "backend",
                    "Alex uses FastAPI.",
                    section="Python and Backend Development",
                ),
            ]
        ),
        default_limit=6,
        score_threshold=0.5,
    )

    chunks = retriever.retrieve("Tell me about Alex FastAPI backend experience")

    assert [chunk.metadata.section for chunk in chunks] == ["Python and Backend Development"]


def test_qdrant_retriever_keeps_link_sections_for_link_queries() -> None:
    retriever = QdrantRetriever(
        embedding_client=FakeEmbeddingClient(),
        store=FakeSearchStore(
            [
                _chunk("links", "GitHub profile.", section="Links"),
                _chunk(
                    "backend",
                    "Alex uses FastAPI.",
                    section="Python and Backend Development",
                ),
            ]
        ),
        default_limit=6,
        score_threshold=0.5,
    )

    chunks = retriever.retrieve("Show me Alex GitHub link")

    assert [chunk.metadata.section for chunk in chunks] == [
        "Links",
        "Python and Backend Development",
    ]


def test_qdrant_retriever_expands_short_sql_queries() -> None:
    fake_embedding_client = FakeEmbeddingClient()
    retriever = QdrantRetriever(
        embedding_client=fake_embedding_client,
        store=FakeSearchStore(
            [
                _chunk(
                    "database",
                    "Alex has SQL experience.",
                    section="Python and Backend Development",
                )
            ]
        ),
        default_limit=6,
        score_threshold=0.4,
    )

    chunks = retriever.retrieve("У Алекса есть опыт с SQL?")

    assert chunks
    assert fake_embedding_client.last_text is not None
    assert "PostgreSQL SQLAlchemy Alembic" in fake_embedding_client.last_text
    assert "experience skills practical work" in fake_embedding_client.last_text


def test_ingestion_replaces_vectors_from_reviewed_public_knowledge() -> None:
    knowledge_dir = _local_knowledge_dir("provider-ingestion")
    (knowledge_dir / "resume.md").write_text(
        _structured_resume_markdown(),
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

    assert summary.loaded_chunks == 2
    assert summary.indexed_chunks == 2
    assert fake_embedding_client.texts == [
        "- Alex builds FastAPI services.",
        "- Alex delivered API automation.",
    ]
    assert fake_vector_store.replaced_chunks[0].metadata.source == "Summary"
    assert fake_vector_store.source_files == (
        "content/public/resume.md",
        "frontend/content/resume.md",
        "resume.md",
        "resume.generated.chunks.json",
    )


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
    assert fake_vector_store.source_files == (
        "content/public/resume.md",
        "frontend/content/resume.md",
        "resume.md",
        "resume.generated.chunks.json",
    )


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
    def __init__(
        self,
        search_points: list[SimpleNamespace] | None = None,
        collection_exists: bool = False,
    ) -> None:
        self.operations: list[str] = []
        self.upserted_points: list[object] = []
        self.indexed_fields: list[tuple[str, object]] = []
        self.deleted_filters: list[tuple[str, object]] = []
        self._search_points = search_points or []
        self._collection_exists = collection_exists

    def collection_exists(self, *, collection_name: str) -> bool:
        self.operations.append("collection_exists")
        return self._collection_exists

    def create_collection(self, **kwargs: object) -> None:
        self.operations.append("create_collection")

    def create_payload_index(
        self,
        *,
        collection_name: str,
        field_name: str,
        field_schema: object,
    ) -> None:
        self.operations.append("create_payload_index")
        self.indexed_fields.append((field_name, getattr(field_schema, "value", field_schema)))

    def delete(self, **kwargs: object) -> None:
        self.operations.append("delete")
        filter_conditions = kwargs["points_selector"].filter.must
        condition = filter_conditions[0]
        self.deleted_filters.append((condition.key, condition.match.value))

    def upsert(self, *, collection_name: str, points: list[object]) -> None:
        self.operations.append("upsert")
        self.upserted_points = points

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(points=self._search_points)


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.last_text: str | None = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.texts = texts
        return [[1.0, 0.0] for _ in texts]

    def embed_text(self, text: str) -> list[float]:
        self.last_text = text
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


class FakeSearchStore:
    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self._chunks = chunks

    def search(
        self,
        *,
        embedding: list[float],
        limit: int,
        score_threshold: float,
    ) -> list[KnowledgeChunk]:
        return self._chunks[:limit]


def _chunk(chunk_id: str, content: str, section: str = "Summary") -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        content=content,
        metadata=ChunkMetadata(
            source="resume.md",
            section=section,
            topic=section.lower().replace(" ", "-"),
        ),
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
        openai_reasoning_effort="low",
        qdrant_url="http://qdrant.test",
        qdrant_api_key="",
        qdrant_collection="alex_public_knowledge",
        rag_top_k=6,
        rag_score_threshold=0.72,
        resend_api_key="",
        contact_target_email="",
        contact_from_email="",
        rate_limiting_enabled=True,
        chat_daily_limit_per_ip=50,
        contact_daily_limit_per_ip=5,
    )


def _local_knowledge_dir(name: str) -> Path:
    test_root = Path.cwd() / ".tmp" / "test-rag-providers" / name
    if test_root.exists():
        for file_path in test_root.iterdir():
            file_path.unlink()
    test_root.mkdir(parents=True, exist_ok=True)
    return test_root


def _structured_resume_markdown() -> str:
    return """
# Summary

## Concise

Visible summary.

## Detailed

Visible detailed summary.

## RAG

#### Answer Facts

- Alex builds FastAPI services.

#### Primary Tags

- fastapi

# Entries

## Sample Project

```yaml
id: sample-project
section: experience
startDate: 2024-01
endDate: present
title: Sample Project
```

### Concise

- Visible concise bullet.

### Detailed

- Visible detailed bullet.

### RAG

#### Answer Facts

- Alex delivered API automation.

#### Primary Tags

- api

# Additional Sections
""".strip()
