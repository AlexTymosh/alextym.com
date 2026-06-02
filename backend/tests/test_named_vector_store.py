from types import SimpleNamespace

import pytest

from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.qdrant_store import QdrantKnowledgeStore


def test_qdrant_store_creates_named_vector_collection() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge_named",
        vector_mode="named",
        client=fake_qdrant,
    )

    store.ensure_collection(vector_size=2)

    vectors_config = fake_qdrant.created_collection_kwargs["vectors_config"]

    assert set(vectors_config) == {"title_dense", "body_dense", "summary_dense"}
    assert vectors_config["body_dense"].size == 2


def test_qdrant_store_upserts_named_vectors() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge_named",
        vector_mode="named",
        client=fake_qdrant,
    )

    store.replace_source_named_vector_chunks(
        chunks=[_chunk()],
        named_embeddings=[
            {
                "title_dense": [1.0, 0.0],
                "body_dense": [0.9, 0.1],
                "summary_dense": [0.8, 0.2],
            }
        ],
        source_files=("resume.generated.chunks.json",),
        vector_size=2,
    )

    point = fake_qdrant.upserted_points[0]

    assert set(point.vector) == {"title_dense", "body_dense", "summary_dense"}
    assert point.vector["body_dense"] == [0.9, 0.1]


def test_qdrant_store_searches_named_query_vector() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge_named",
        vector_mode="named",
        query_vector_name="summary_dense",
        client=fake_qdrant,
    )

    store.search(embedding=[0.1, 0.2], limit=3, score_threshold=0.5)

    assert fake_qdrant.last_query_kwargs["query"] == [0.1, 0.2]
    assert fake_qdrant.last_query_kwargs["using"] == "summary_dense"


def test_named_collection_rejects_single_vector_ingestion() -> None:
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge_named",
        vector_mode="named",
        client=FakeQdrantClient(),
    )

    with pytest.raises(RuntimeError, match="Single-vector ingestion"):
        store.replace_source_chunks(
            chunks=[_chunk()],
            embeddings=[[1.0, 0.0]],
            source_files=("resume.md",),
            vector_size=2,
        )


class FakeQdrantClient:
    def __init__(self) -> None:
        self.created_collection_kwargs: dict[str, object] = {}
        self.upserted_points: list[object] = []
        self.last_query_kwargs: dict[str, object] = {}

    def collection_exists(self, *, collection_name: str) -> bool:
        return False

    def create_collection(self, **kwargs: object) -> None:
        self.created_collection_kwargs = kwargs

    def create_payload_index(self, **kwargs: object) -> None:
        return None

    def delete(self, **kwargs: object) -> None:
        return None

    def upsert(self, *, collection_name: str, points: list[object]) -> None:
        self.upserted_points = points

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        self.last_query_kwargs = kwargs
        return SimpleNamespace(points=[])


def _chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        id="resume:hard-skills:rag",
        content="- Alex uses Python.",
        metadata=ChunkMetadata(
            source="Hard Skills",
            section="experience",
            topic="hard-skills",
        ),
    )
