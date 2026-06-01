from types import SimpleNamespace

from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.qdrant_store import QdrantKnowledgeStore


def test_qdrant_store_preserves_structured_rag_payload() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge",
        client=fake_qdrant,
    )
    chunk = KnowledgeChunk(
        id="resume:hard-skills:rag",
        content="- Alex uses Python.",
        metadata=ChunkMetadata(
            source="Hard Skills",
            section="experience",
            topic="hard-skills",
            tags=("python", "automation"),
            extra={
                "source_file": "resume.generated.chunks.json",
                "parent_id": "resume:hard-skills",
                "source": {"title": "Hard Skills", "section": "experience"},
                "payload": {"topic": "hard-skills"},
                "answer_facts": ["Alex uses Python."],
                "retrieval_hints": ["Useful for skill questions."],
                "vector_inputs": {"body_dense": "Hard Skills\n\nAlex uses Python."},
                "retrieval": {"modes": ["dense"]},
            },
        ),
    )

    store.replace_source_chunks(
        chunks=[chunk],
        embeddings=[[0.1, 0.2]],
        source_files=("resume.md", "resume.generated.chunks.json"),
        vector_size=2,
    )

    payload = fake_qdrant.upserted_points[0].payload

    assert payload["source"] == "Hard Skills"
    assert payload["source_file"] == "resume.generated.chunks.json"
    assert payload["parent_id"] == "resume:hard-skills"
    assert payload["source_details"] == {
        "title": "Hard Skills",
        "section": "experience",
    }
    assert payload["rag_payload"] == {"topic": "hard-skills"}
    assert payload["answer_facts"] == ["Alex uses Python."]
    assert payload["vector_inputs"] == {"body_dense": "Hard Skills\n\nAlex uses Python."}


def test_qdrant_store_deletes_legacy_and_generated_sources_separately() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge",
        client=fake_qdrant,
    )

    store.delete_sources(("resume.md", "resume.generated.chunks.json"))

    assert fake_qdrant.delete_filters == [
        ("source_file", "resume.md"),
        ("source", "resume.md"),
        ("source_file", "resume.generated.chunks.json"),
        ("source", "resume.generated.chunks.json"),
    ]


def test_qdrant_store_maps_structured_payload_back_to_chunk() -> None:
    fake_qdrant = FakeQdrantClient(
        search_points=[
            SimpleNamespace(
                id="point-1",
                payload={
                    "chunk_id": "resume:hard-skills:rag",
                    "content": "- Alex uses Python.",
                    "source": "Hard Skills",
                    "source_file": "resume.generated.chunks.json",
                    "section": "experience",
                    "topic": "hard-skills",
                    "visibility": "public",
                    "confidence": "self-reported",
                    "source_confidence": "medium",
                    "tags": ["python", "automation"],
                    "parent_id": "resume:hard-skills",
                    "vector_inputs": {"body_dense": "text"},
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

    chunks = store.search(embedding=[0.1, 0.2], limit=1, score_threshold=0.7)

    assert len(chunks) == 1
    assert chunks[0].metadata.source == "Hard Skills"
    assert chunks[0].metadata.extra["source_file"] == "resume.generated.chunks.json"
    assert chunks[0].metadata.extra["parent_id"] == "resume:hard-skills"


class FakeQdrantClient:
    def __init__(
        self,
        search_points: list[SimpleNamespace] | None = None,
        collection_exists: bool = False,
    ) -> None:
        self.operations: list[str] = []
        self.upserted_points: list[object] = []
        self.delete_filters: list[tuple[str, str]] = []
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

    def delete(self, **kwargs: object) -> None:
        self.operations.append("delete")
        filter_conditions = kwargs["points_selector"].filter.must
        condition = filter_conditions[0]
        self.delete_filters.append((condition.key, condition.match.value))

    def upsert(self, *, collection_name: str, points: list[object]) -> None:
        self.operations.append("upsert")
        self.upserted_points = points

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(points=self._search_points)
