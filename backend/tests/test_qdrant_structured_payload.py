from types import SimpleNamespace

from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.qdrant_store import QdrantKnowledgeStore


def test_qdrant_store_preserves_structured_rag_payload() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="public_knowledge",
        client=fake_qdrant,
    )
    chunk = KnowledgeChunk(
        id="case:case-sample:analysis",
        content="- The Owner analysed a process.",
        metadata=ChunkMetadata(
            source="Sample Case",
            section="experience",
            topic="sample-analysis",
            tags=("analysis", "case-study"),
            extra={
                "source_file": "content/public/case-studies/sample.case.md",
                "parent_id": "case:case-sample",
                "document_type": "case-study",
                "source_group": "case-studies",
                "case_id": "case-sample",
                "case_section": "analysis",
                "organization": "Example Ltd",
                "dataset_version": "a" * 64,
                "source": {
                    "title": "Sample Case",
                    "section": "experience",
                    "organization": "Example Ltd",
                },
                "payload": {"topic": "sample-analysis"},
                "answer_facts": ["The Owner analysed a process."],
                "retrieval_hints": ["Useful for process-analysis questions."],
                "vector_inputs": {"body_dense": "Sample Case\n\nProcess analysis."},
                "retrieval": {"modes": ["dense"]},
            },
        ),
    )

    store.replace_source_chunks(
        chunks=[chunk],
        embeddings=[[0.1, 0.2]],
        source_files=("content/public/case-studies/sample.case.md",),
        vector_size=2,
    )

    payload = fake_qdrant.upserted_points[0].payload

    assert payload["source"] == "Sample Case"
    assert payload["source_file"] == "content/public/case-studies/sample.case.md"
    assert payload["parent_id"] == "case:case-sample"
    assert payload["document_type"] == "case-study"
    assert payload["source_group"] == "case-studies"
    assert payload["case_id"] == "case-sample"
    assert payload["case_section"] == "analysis"
    assert payload["organization"] == "Example Ltd"
    assert payload["dataset_version"] == "a" * 64
    assert payload["source_details"]["organization"] == "Example Ltd"
    assert payload["rag_payload"] == {"topic": "sample-analysis"}


def test_qdrant_store_deletes_legacy_and_generated_sources_separately() -> None:
    fake_qdrant = FakeQdrantClient()
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="public_knowledge",
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
                score=0.87,
                payload={
                    "chunk_id": "case:case-sample:analysis",
                    "content": "- The Owner analysed a process.",
                    "source": "Sample Case",
                    "source_file": "content/public/case-studies/sample.case.md",
                    "section": "experience",
                    "topic": "sample-analysis",
                    "visibility": "public",
                    "confidence": "self-reported",
                    "source_confidence": "medium",
                    "tags": ["analysis", "case-study"],
                    "parent_id": "case:case-sample",
                    "document_type": "case-study",
                    "source_group": "case-studies",
                    "case_id": "case-sample",
                    "case_section": "analysis",
                    "organization": "Example Ltd",
                    "dataset_version": "a" * 64,
                    "vector_inputs": {"body_dense": "text"},
                },
            )
        ]
    )
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="public_knowledge",
        client=fake_qdrant,
    )

    chunks = store.search(embedding=[0.1, 0.2], limit=1, score_threshold=0.7)

    assert len(chunks) == 1
    extra = chunks[0].metadata.extra
    assert extra["source_group"] == "case-studies"
    assert extra["case_id"] == "case-sample"
    assert extra["case_section"] == "analysis"
    assert extra["dataset_version"] == "a" * 64
    assert extra["retrieval_score"] == 0.87


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
        wait: bool | None = None,
    ) -> None:
        self.operations.append("create_payload_index")

    def delete(self, **kwargs: object) -> None:
        self.operations.append("delete")
        filter_conditions = kwargs["points_selector"].filter.must
        condition = filter_conditions[0]
        self.delete_filters.append((condition.key, condition.match.value))

    def upsert(
        self,
        *,
        collection_name: str,
        points: list[object],
        wait: bool | None = None,
    ) -> None:
        self.operations.append("upsert")
        self.upserted_points = points

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(points=self._search_points)
