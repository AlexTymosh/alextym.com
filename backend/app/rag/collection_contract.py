from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import models

from app.core.config import Settings
from app.rag.errors import RagCollectionContractError, RetrievalError
from app.rag.vector_config import (
    DEFAULT_QUERY_VECTOR_NAME,
    NAMED_DENSE_VECTOR_NAMES,
    DenseVectorName,
    VectorMode,
    normalise_query_vector_name,
    normalise_vector_mode,
)

BASE_PAYLOAD_INDEXES = (
    "source",
    "source_file",
    "section",
    "topic",
    "visibility",
    "tags",
)
VERSIONED_PAYLOAD_INDEXES = (
    "document_type",
    "source_group",
    "case_id",
    "case_section",
    "dataset_version",
)
PUBLIC_SOURCE_GROUPS = ("resume", "case-studies")
RUNTIME_VECTOR_MODE: VectorMode = "single"
READABLE_COLLECTION_STATUSES = {"green", "yellow"}


@dataclass(frozen=True)
class RagCollectionContract:
    vector_mode: VectorMode
    vector_size: int
    query_vector_name: DenseVectorName
    required_payload_indexes: tuple[str, ...] = (
        *BASE_PAYLOAD_INDEXES,
        *VERSIONED_PAYLOAD_INDEXES,
    )
    required_source_groups: tuple[str, ...] = PUBLIC_SOURCE_GROUPS

    @classmethod
    def for_runtime(cls, settings: Settings) -> "RagCollectionContract":
        configured_mode = normalise_vector_mode(settings.qdrant_vector_mode)
        if configured_mode != RUNTIME_VECTOR_MODE:
            raise RagCollectionContractError(
                "Runtime RAG retrieval requires the canonical single-vector mode.",
                code="vector_mode_not_supported",
            )
        if settings.openai_embedding_dimensions <= 0:
            raise RagCollectionContractError(
                "Runtime embedding dimensions must be positive.",
                code="vector_size_invalid",
            )
        return cls(
            vector_mode=RUNTIME_VECTOR_MODE,
            vector_size=settings.openai_embedding_dimensions,
            query_vector_name=DEFAULT_QUERY_VECTOR_NAME,
        )

    @classmethod
    def for_store(
        cls,
        *,
        vector_mode: str,
        vector_size: int,
        query_vector_name: str,
        required_source_groups: tuple[str, ...] = PUBLIC_SOURCE_GROUPS,
    ) -> "RagCollectionContract":
        return cls(
            vector_mode=normalise_vector_mode(vector_mode),
            vector_size=vector_size,
            query_vector_name=normalise_query_vector_name(query_vector_name),
            required_source_groups=required_source_groups,
        )


def payload_index_fields(*, include_versioned: bool) -> tuple[str, ...]:
    if include_versioned:
        return (*BASE_PAYLOAD_INDEXES, *VERSIONED_PAYLOAD_INDEXES)
    return BASE_PAYLOAD_INDEXES


def validate_qdrant_collection_contract(
    *,
    client: Any,
    collection_name: str,
    contract: RagCollectionContract,
) -> None:
    try:
        if not client.collection_exists(collection_name=collection_name):
            raise RagCollectionContractError(
                "Configured Qdrant collection does not exist.",
                code="collection_missing",
            )

        collection = client.get_collection(collection_name=collection_name)
        _validate_collection_status(collection)
        _validate_vector_config(collection, contract)
        _validate_payload_indexes(collection, contract)
        _validate_point_count(collection)
        _validate_source_groups(
            client=client,
            collection_name=collection_name,
            source_groups=contract.required_source_groups,
        )
    except RagCollectionContractError:
        raise
    except Exception as exc:
        raise RetrievalError(
            "Qdrant collection contract check failed.",
            stage="collection_contract",
            code="collection_check_failed",
            retryable=True,
        ) from exc


def _validate_collection_status(collection: Any) -> None:
    status = _enum_value(getattr(collection, "status", None))
    if status not in READABLE_COLLECTION_STATUSES:
        raise RagCollectionContractError(
            "Configured Qdrant collection is not readable.",
            code="collection_not_ready",
        )


def _validate_vector_config(
    collection: Any,
    contract: RagCollectionContract,
) -> None:
    config = getattr(collection, "config", None)
    params = getattr(config, "params", None)
    vectors = getattr(params, "vectors", None)

    if contract.vector_mode == "single":
        if isinstance(vectors, dict) or vectors is None:
            raise RagCollectionContractError(
                "Qdrant vector mode does not match the runtime contract.",
                code="vector_mode_mismatch",
            )
        _validate_vector_params(vectors, expected_size=contract.vector_size)
        return

    if not isinstance(vectors, dict):
        raise RagCollectionContractError(
            "Qdrant vector mode does not match the runtime contract.",
            code="vector_mode_mismatch",
        )

    missing_vectors = set(NAMED_DENSE_VECTOR_NAMES).difference(vectors)
    if missing_vectors:
        raise RagCollectionContractError(
            "Qdrant named-vector collection is incomplete.",
            code="query_vector_missing",
        )
    if contract.query_vector_name not in vectors:
        raise RagCollectionContractError(
            "Configured Qdrant query vector is missing.",
            code="query_vector_missing",
        )
    for vector_name in NAMED_DENSE_VECTOR_NAMES:
        _validate_vector_params(vectors[vector_name], expected_size=contract.vector_size)


def _validate_vector_params(vector_params: Any, *, expected_size: int) -> None:
    if getattr(vector_params, "size", None) != expected_size:
        raise RagCollectionContractError(
            "Qdrant vector dimensions do not match the embedding contract.",
            code="vector_size_mismatch",
        )
    if _enum_value(getattr(vector_params, "distance", None)) != "cosine":
        raise RagCollectionContractError(
            "Qdrant vector distance does not match the retrieval contract.",
            code="vector_distance_mismatch",
        )


def _validate_payload_indexes(
    collection: Any,
    contract: RagCollectionContract,
) -> None:
    payload_schema = getattr(collection, "payload_schema", None)
    if not isinstance(payload_schema, dict):
        payload_schema = {}

    for field_name in contract.required_payload_indexes:
        index_info = payload_schema.get(field_name)
        if index_info is None:
            raise RagCollectionContractError(
                "Qdrant payload index required by retrieval is missing.",
                code="payload_index_missing",
            )
        data_type = _enum_value(getattr(index_info, "data_type", index_info))
        if data_type != "keyword":
            raise RagCollectionContractError(
                "Qdrant payload index type does not match the retrieval contract.",
                code="payload_index_type_mismatch",
            )


def _validate_point_count(collection: Any) -> None:
    points_count = getattr(collection, "points_count", None)
    if not isinstance(points_count, int) or points_count <= 0:
        raise RagCollectionContractError(
            "Configured Qdrant collection does not contain public knowledge.",
            code="collection_empty",
        )


def _validate_source_groups(
    *,
    client: Any,
    collection_name: str,
    source_groups: tuple[str, ...],
) -> None:
    for source_group in source_groups:
        result = client.count(
            collection_name=collection_name,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="visibility",
                        match=models.MatchValue(value="public"),
                    ),
                    models.FieldCondition(
                        key="source_group",
                        match=models.MatchValue(value=source_group),
                    ),
                ]
            ),
            exact=True,
        )
        count = getattr(result, "count", None)
        if not isinstance(count, int) or count <= 0:
            raise RagCollectionContractError(
                "Qdrant collection is missing an expected public source group.",
                code="source_group_missing",
            )


def _enum_value(value: object) -> str:
    raw_value = getattr(value, "value", value)
    return str(raw_value).strip().casefold()
