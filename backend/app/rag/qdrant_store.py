import uuid
from collections.abc import Iterable
from typing import Any

from qdrant_client import QdrantClient, models

from app.core.config import Settings
from app.llm.client import ProviderConfigurationError, ProviderRequestError
from app.rag.models import ChunkMetadata, KnowledgeChunk, RetrievalFilter
from app.rag.vector_config import DenseVectorName, NAMED_DENSE_VECTOR_NAMES
from app.rag.vector_config import VectorMode, normalise_query_vector_name
from app.rag.vector_config import normalise_vector_mode
from app.core.confidence import Confidence

NamedEmbeddings = dict[DenseVectorName, list[float]]


class QdrantKnowledgeStore:
    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        collection_name: str,
        vector_mode: str = "single",
        query_vector_name: str = "body_dense",
        client: Any | None = None,
    ) -> None:
        if not url and client is None:
            raise ProviderConfigurationError("Qdrant URL is not configured.")
        if not collection_name:
            raise ProviderConfigurationError("Qdrant collection is not configured.")

        self._client = client or QdrantClient(url=url, api_key=api_key or None)
        self._collection_name = collection_name
        self._vector_mode = normalise_vector_mode(vector_mode)
        self._query_vector_name = normalise_query_vector_name(query_vector_name)

    @classmethod
    def from_settings(cls, settings: Settings) -> "QdrantKnowledgeStore":
        return cls(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection_name=settings.qdrant_collection,
            vector_mode=settings.qdrant_vector_mode,
            query_vector_name=settings.qdrant_query_vector_name,
        )

    def ensure_collection(self, *, vector_size: int) -> None:
        if vector_size <= 0:
            raise ProviderConfigurationError("Qdrant vector size must be positive.")

        try:
            collection_exists = self._client.collection_exists(
                collection_name=self._collection_name
            )
            if not collection_exists:
                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=_vectors_config(
                        vector_size=vector_size,
                        vector_mode=self._vector_mode,
                    ),
                )
            self._ensure_payload_indexes()
        except Exception as exc:
            raise ProviderRequestError(f"Qdrant collection setup failed: {exc}") from exc

    def _ensure_payload_indexes(self) -> None:
        for field_name in (
            "source",
            "source_file",
            "section",
            "topic",
            "visibility",
            "tags",
        ):
            self._ensure_payload_index(field_name)

    def _ensure_payload_index(self, field_name: str) -> None:
        try:
            self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            if "already" in str(exc).lower():
                return
            raise

    def replace_source_chunks(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
        source_files: Iterable[str],
        vector_size: int,
    ) -> None:
        if self._vector_mode == "named":
            raise ProviderConfigurationError(
                "Single-vector ingestion cannot target a named-vector collection. "
                "Use replace_source_named_vector_chunks instead."
            )
        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must have the same length.")

        self.ensure_collection(vector_size=vector_size)
        self.delete_sources(source_files)
        if chunks:
            self.upsert_chunks(chunks=chunks, embeddings=embeddings)

    def replace_source_named_vector_chunks(
        self,
        *,
        chunks: list[KnowledgeChunk],
        named_embeddings: list[NamedEmbeddings],
        source_files: Iterable[str],
        vector_size: int,
    ) -> None:
        if len(chunks) != len(named_embeddings):
            raise ValueError("Chunks and named embeddings must have the same length.")

        self.ensure_collection(vector_size=vector_size)
        self.delete_sources(source_files)
        if chunks:
            self.upsert_named_vector_chunks(
                chunks=chunks,
                named_embeddings=named_embeddings,
            )

    def delete_sources(self, source_files: Iterable[str]) -> None:
        for source_file in source_files:
            self._delete_by_payload_field(field_name="source_file", value=source_file)
            self._delete_by_payload_field(field_name="source", value=source_file)

    def _delete_by_payload_field(self, *, field_name: str, value: str) -> None:
        try:
            self._client.delete(
                collection_name=self._collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key=field_name,
                                match=models.MatchValue(value=value),
                            )
                        ]
                    ),
                ),
            )
        except Exception as exc:
            raise ProviderRequestError(
                f"Qdrant source cleanup failed for {field_name}={value!r}: {exc}"
            ) from exc

    def upsert_chunks(
        self,
        *,
        chunks: list[KnowledgeChunk],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must have the same length.")
        if not chunks:
            return

        points = [
            models.PointStruct(
                id=_point_id(chunk),
                vector=embedding,
                payload=_payload_from_chunk(chunk),
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]

        try:
            self._client.upsert(collection_name=self._collection_name, points=points)
        except Exception as exc:
            raise ProviderRequestError(f"Qdrant upsert failed: {exc}") from exc

    def upsert_named_vector_chunks(
        self,
        *,
        chunks: list[KnowledgeChunk],
        named_embeddings: list[NamedEmbeddings],
    ) -> None:
        if len(chunks) != len(named_embeddings):
            raise ValueError("Chunks and named embeddings must have the same length.")
        if not chunks:
            return

        points = [
            models.PointStruct(
                id=_point_id(chunk),
                vector=dict(named_embedding),
                payload=_payload_from_chunk(chunk),
            )
            for chunk, named_embedding in zip(chunks, named_embeddings, strict=True)
        ]

        try:
            self._client.upsert(collection_name=self._collection_name, points=points)
        except Exception as exc:
            raise ProviderRequestError(f"Qdrant upsert failed: {exc}") from exc

    def search(
        self,
        *,
        embedding: list[float],
        limit: int,
        score_threshold: float,
        payload_filter: RetrievalFilter | None = None,
    ) -> list[KnowledgeChunk]:
        if not embedding:
            return []

        query_kwargs: dict[str, Any] = {
            "collection_name": self._collection_name,
            "query": embedding,
            "query_filter": _build_query_filter(payload_filter),
            "limit": limit,
            "score_threshold": score_threshold,
            "with_payload": True,
        }
        if self._vector_mode == "named":
            query_kwargs["using"] = self._query_vector_name

        try:
            query_response = self._client.query_points(**query_kwargs)
        except Exception as exc:
            raise ProviderRequestError(f"Qdrant search failed: {exc}") from exc

        points = getattr(query_response, "points", query_response)
        return [_chunk_from_point(point) for point in points]


def _vectors_config(
    *,
    vector_size: int,
    vector_mode: VectorMode,
) -> models.VectorParams | dict[str, models.VectorParams]:
    vector_params = models.VectorParams(
        size=vector_size,
        distance=models.Distance.COSINE,
    )
    if vector_mode == "single":
        return vector_params

    return {vector_name: vector_params for vector_name in NAMED_DENSE_VECTOR_NAMES}


def _build_query_filter(
    payload_filter: RetrievalFilter | None,
) -> models.Filter | None:
    if payload_filter is None:
        return None

    must: list[models.FieldCondition] = []
    should: list[models.FieldCondition] = []

    if payload_filter.visibility:
        must.append(
            models.FieldCondition(
                key="visibility",
                match=models.MatchValue(value=payload_filter.visibility),
            )
        )

    should.extend(_match_any_conditions("topic", payload_filter.topic_any))
    should.extend(_match_any_conditions("tags", payload_filter.tag_any))
    should.extend(_match_any_conditions("section", payload_filter.section_any))

    if not must and not should:
        return None

    return models.Filter(must=must or None, should=should or None)


def _match_any_conditions(
    field_name: str,
    values: tuple[str, ...],
) -> list[models.FieldCondition]:
    if not values:
        return []

    return [
        models.FieldCondition(
            key=field_name,
            match=models.MatchAny(any=list(values)),
        )
    ]


def _point_id(chunk: KnowledgeChunk) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"alextym:{chunk.id}"))


def _payload_from_chunk(chunk: KnowledgeChunk) -> dict[str, Any]:
    extra = chunk.metadata.extra
    source_file = _text_or_default(extra.get("source_file"), chunk.metadata.source)
    payload: dict[str, Any] = {
        "chunk_id": chunk.id,
        "content": chunk.content,
        "source": chunk.metadata.source,
        "source_file": source_file,
        "section": chunk.metadata.section,
        "topic": chunk.metadata.topic,
        "visibility": chunk.metadata.visibility,
        "confidence": chunk.metadata.confidence,
        "source_confidence": chunk.metadata.source_confidence,
        "tags": list(chunk.metadata.tags),
    }

    optional_payload = {
        "parent_id": extra.get("parent_id"),
        "schema_version": extra.get("schema_version"),
        "source_details": extra.get("source"),
        "rag_payload": extra.get("payload"),
        "answer_facts": extra.get("answer_facts"),
        "retrieval_hints": extra.get("retrieval_hints"),
        "vector_inputs": extra.get("vector_inputs"),
        "retrieval": extra.get("retrieval"),
    }

    for key, value in optional_payload.items():
        if value not in (None, "", [], {}):
            payload[key] = value

    return payload


def _chunk_from_point(point: Any) -> KnowledgeChunk:
    payload = getattr(point, "payload", None) or {}
    return KnowledgeChunk(
        id=str(payload.get("chunk_id") or getattr(point, "id", "")),
        content=str(payload.get("content") or ""),
        metadata=ChunkMetadata(
            source=str(payload.get("source") or "unknown"),
            section=str(payload.get("section") or "Document"),
            topic=str(payload.get("topic") or "document"),
            visibility=str(payload.get("visibility") or "public"),
            confidence=str(payload.get("confidence") or "self-reported"),
            source_confidence=_source_confidence(payload.get("source_confidence")),
            tags=tuple(str(tag) for tag in payload.get("tags", []) or []),
            extra=_extra_from_payload(payload, point=point),
        ),
    )


def _extra_from_payload(payload: dict[str, Any], *, point: Any) -> dict[str, Any]:
    extra_keys = {
        "source_file",
        "parent_id",
        "schema_version",
        "source_details",
        "rag_payload",
        "answer_facts",
        "retrieval_hints",
        "vector_inputs",
        "retrieval",
    }
    extra = {
        key: value
        for key, value in payload.items()
        if key in extra_keys and value not in (None, "", [], {})
    }
    score = getattr(point, "score", None)
    if isinstance(score, (int, float)):
        extra["retrieval_score"] = float(score)
    return extra


def _text_or_default(value: object, default: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _source_confidence(value: object) -> Confidence:
    return value if value in {"low", "medium", "high"} else "medium"
