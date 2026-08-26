from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.rag.collection_contract import RagCollectionContract
from app.rag.errors import RagCollectionContractError
from app.rag.qdrant_store import QdrantKnowledgeStore


def test_collection_contract_accepts_current_single_vector_schema() -> None:
    client = ContractQdrantClient()
    store = _store(client)

    store.validate_contract(_contract())

    assert client.counted_source_groups == ["resume", "case-studies"]


def test_collection_contract_rejects_missing_source_group_index() -> None:
    client = ContractQdrantClient(missing_indexes={"source_group"})

    with pytest.raises(RagCollectionContractError) as exc_info:
        _store(client).validate_contract(_contract())

    assert exc_info.value.code == "payload_index_missing"


def test_collection_contract_rejects_named_vectors_for_single_runtime() -> None:
    client = ContractQdrantClient(vector_mode="named")

    with pytest.raises(RagCollectionContractError) as exc_info:
        _store(client).validate_contract(_contract())

    assert exc_info.value.code == "vector_mode_mismatch"


def test_collection_contract_rejects_wrong_vector_dimensions() -> None:
    client = ContractQdrantClient(vector_size=3072)

    with pytest.raises(RagCollectionContractError) as exc_info:
        _store(client).validate_contract(_contract())

    assert exc_info.value.code == "vector_size_mismatch"


def test_collection_contract_rejects_empty_collection() -> None:
    client = ContractQdrantClient(points_count=0)

    with pytest.raises(RagCollectionContractError) as exc_info:
        _store(client).validate_contract(_contract())

    assert exc_info.value.code == "collection_empty"


def test_collection_contract_rejects_missing_public_source_group() -> None:
    client = ContractQdrantClient(source_group_counts={"resume": 10, "case-studies": 0})

    with pytest.raises(RagCollectionContractError) as exc_info:
        _store(client).validate_contract(_contract())

    assert exc_info.value.code == "source_group_missing"


def test_runtime_contract_rejects_named_vector_configuration() -> None:
    settings = replace(get_settings(), qdrant_vector_mode="named")

    with pytest.raises(RagCollectionContractError) as exc_info:
        RagCollectionContract.for_runtime(settings)

    assert exc_info.value.code == "vector_mode_not_supported"


class ContractQdrantClient:
    def __init__(
        self,
        *,
        vector_mode: str = "single",
        vector_size: int = 1536,
        points_count: int = 115,
        missing_indexes: set[str] | None = None,
        source_group_counts: dict[str, int] | None = None,
    ) -> None:
        self._vector_mode = vector_mode
        self._vector_size = vector_size
        self._points_count = points_count
        self._missing_indexes = missing_indexes or set()
        self._source_group_counts = source_group_counts or {
            "resume": 20,
            "case-studies": 95,
        }
        self.counted_source_groups: list[str] = []

    def collection_exists(self, *, collection_name: str) -> bool:
        return True

    def get_collection(self, *, collection_name: str) -> SimpleNamespace:
        vector_params = SimpleNamespace(size=self._vector_size, distance="Cosine")
        vectors: object = vector_params
        if self._vector_mode == "named":
            vectors = {
                "title_dense": vector_params,
                "body_dense": vector_params,
                "summary_dense": vector_params,
            }
        required_indexes = {
            "source",
            "source_file",
            "section",
            "topic",
            "visibility",
            "tags",
            "document_type",
            "source_group",
            "case_id",
            "case_section",
            "dataset_version",
        }
        payload_schema = {
            field: SimpleNamespace(data_type="keyword")
            for field in required_indexes.difference(self._missing_indexes)
        }
        return SimpleNamespace(
            status="green",
            points_count=self._points_count,
            config=SimpleNamespace(params=SimpleNamespace(vectors=vectors)),
            payload_schema=payload_schema,
        )

    def count(
        self,
        *,
        collection_name: str,
        count_filter: object,
        exact: bool,
    ) -> SimpleNamespace:
        source_group = count_filter.must[1].match.value
        self.counted_source_groups.append(source_group)
        return SimpleNamespace(count=self._source_group_counts[source_group])


def _contract() -> RagCollectionContract:
    return RagCollectionContract.for_store(
        vector_mode="single",
        vector_size=1536,
        query_vector_name="body_dense",
    )


def _store(client: ContractQdrantClient) -> QdrantKnowledgeStore:
    return QdrantKnowledgeStore(
        url="",
        api_key="",
        collection_name="alex_public_knowledge",
        client=client,
    )
