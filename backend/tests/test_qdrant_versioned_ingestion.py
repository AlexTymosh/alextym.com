from types import SimpleNamespace

import pytest

from app.llm.client import ProviderRequestError
from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.qdrant_store import QdrantKnowledgeStore

DATASET_VERSION = "a" * 64


def test_versioned_ingestion_upserts_before_deleting_stale_points() -> None:
    client = FakeQdrantClient(collection_exists=True)
    store = _store(client)

    store.replace_versioned_chunks(
        chunks=[_resume_chunk(), _case_chunk()],
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
        source_groups=("resume", "case-studies"),
        dataset_version=DATASET_VERSION,
        legacy_source_files=(
            "content/public/resume.md",
            "content/public/case-studies/sample.case.md",
        ),
        vector_size=2,
    )

    upsert_position = client.operations.index("upsert")
    delete_positions = [
        index for index, operation in enumerate(client.operations) if operation == "delete"
    ]
    assert delete_positions
    assert all(upsert_position < position for position in delete_positions)
    assert client.upsert_wait is True
    assert all(call["wait"] is True for call in client.delete_calls)

    stale_resume = client.delete_calls[0]["filter"]
    stale_cases = client.delete_calls[1]["filter"]
    assert stale_resume.must[0].key == "source_group"
    assert stale_resume.must[0].match.value == "resume"
    assert stale_resume.must_not[0].key == "dataset_version"
    assert stale_resume.must_not[0].match.value == DATASET_VERSION
    assert stale_cases.must[0].match.value == "case-studies"

    legacy_resume = client.delete_calls[2]["filter"]
    assert legacy_resume.must[0].key == "source_file"
    assert legacy_resume.must[0].match.value == "content/public/resume.md"
    assert legacy_resume.must_not[0].key == "dataset_version"
    assert legacy_resume.must_not[0].match.value == DATASET_VERSION


def test_versioned_ingestion_preserves_new_payload_fields() -> None:
    client = FakeQdrantClient(collection_exists=True)
    store = _store(client)

    store.replace_versioned_chunks(
        chunks=[_case_chunk()],
        embeddings=[[0.0, 1.0]],
        source_groups=("case-studies",),
        dataset_version=DATASET_VERSION,
        legacy_source_files=("content/public/case-studies/sample.case.md",),
        vector_size=2,
    )

    payload = client.upserted_points[0].payload
    assert payload["document_type"] == "case-study"
    assert payload["source_group"] == "case-studies"
    assert payload["case_id"] == "case-sample"
    assert payload["case_section"] == "analysis"
    assert payload["organization"] == "Example Ltd"
    assert payload["parent_id"] == "case:case-sample"
    assert payload["dataset_version"] == DATASET_VERSION


def test_versioned_ingestion_creates_only_filterable_new_indexes() -> None:
    client = FakeQdrantClient(collection_exists=True)
    store = _store(client)

    store.ensure_collection(
        vector_size=2,
        include_versioned_indexes=True,
        wait_for_indexes=True,
    )

    fields = set(client.payload_indexes)
    assert {
        "document_type",
        "source_group",
        "case_id",
        "case_section",
        "dataset_version",
    }.issubset(fields)
    assert "organization" not in fields
    assert "parent_id" not in fields
    assert all(wait is True for _, wait in client.payload_indexes.values())


def test_upsert_failure_does_not_delete_existing_dataset() -> None:
    client = FakeQdrantClient(collection_exists=True, fail_upsert=True)
    store = _store(client)

    with pytest.raises(ProviderRequestError, match="upsert failed"):
        store.replace_versioned_chunks(
            chunks=[_resume_chunk()],
            embeddings=[[1.0, 0.0]],
            source_groups=("resume",),
            dataset_version=DATASET_VERSION,
            legacy_source_files=("content/public/resume.md",),
            vector_size=2,
        )

    assert client.delete_calls == []


def test_version_validation_fails_before_qdrant_operations() -> None:
    client = FakeQdrantClient(collection_exists=True)
    store = _store(client)
    chunk = _resume_chunk(dataset_version="different")

    with pytest.raises(ValueError, match="inconsistent dataset version"):
        store.replace_versioned_chunks(
            chunks=[chunk],
            embeddings=[[1.0, 0.0]],
            source_groups=("resume",),
            dataset_version=DATASET_VERSION,
            legacy_source_files=("content/public/resume.md",),
            vector_size=2,
        )

    assert client.operations == []


def test_named_versioned_ingestion_uses_same_safe_order() -> None:
    client = FakeQdrantClient(collection_exists=True)
    store = QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="public_knowledge",
        vector_mode="named",
        client=client,
    )

    store.replace_versioned_named_vector_chunks(
        chunks=[_resume_chunk()],
        named_embeddings=[
            {
                "title_dense": [1.0, 0.0],
                "body_dense": [0.9, 0.1],
                "summary_dense": [0.8, 0.2],
            }
        ],
        source_groups=("resume",),
        dataset_version=DATASET_VERSION,
        legacy_source_files=("content/public/resume.md",),
        vector_size=2,
    )

    assert client.operations.index("upsert") < client.operations.index("delete")
    assert set(client.upserted_points[0].vector) == {
        "title_dense",
        "body_dense",
        "summary_dense",
    }


class FakeQdrantClient:
    def __init__(
        self,
        *,
        collection_exists: bool,
        fail_upsert: bool = False,
    ) -> None:
        self._collection_exists = collection_exists
        self._fail_upsert = fail_upsert
        self.operations: list[str] = []
        self.payload_indexes: dict[str, tuple[object, bool]] = {}
        self.upserted_points: list[object] = []
        self.upsert_wait: bool | None = None
        self.delete_calls: list[dict[str, object]] = []

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
        wait: bool,
    ) -> None:
        self.operations.append("create_payload_index")
        self.payload_indexes[field_name] = (field_schema, wait)

    def upsert(
        self,
        *,
        collection_name: str,
        points: list[object],
        wait: bool | None = None,
    ) -> None:
        self.operations.append("upsert")
        if self._fail_upsert:
            raise RuntimeError("upsert failed")
        self.upserted_points = points
        self.upsert_wait = wait

    def delete(
        self,
        *,
        collection_name: str,
        points_selector: object,
        wait: bool | None = None,
    ) -> None:
        self.operations.append("delete")
        self.delete_calls.append(
            {
                "filter": points_selector.filter,
                "wait": wait,
            }
        )

    def query_points(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(points=[])


def _store(client: FakeQdrantClient) -> QdrantKnowledgeStore:
    return QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="public_knowledge",
        client=client,
    )


def _resume_chunk(*, dataset_version: str = DATASET_VERSION) -> KnowledgeChunk:
    return KnowledgeChunk(
        id="resume:summary:rag",
        content="- The Owner has a public profile.",
        metadata=ChunkMetadata(
            source="Summary",
            section="summary",
            topic="summary",
            tags=("resume",),
            extra={
                "source_file": "content/public/resume.md",
                "parent_id": "resume:summary",
                "document_type": "resume",
                "source_group": "resume",
                "dataset_version": dataset_version,
            },
        ),
    )


def _case_chunk() -> KnowledgeChunk:
    return KnowledgeChunk(
        id="case:case-sample:analysis",
        content="- The Owner analysed a documented process.",
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
                "dataset_version": DATASET_VERSION,
            },
        ),
    )
