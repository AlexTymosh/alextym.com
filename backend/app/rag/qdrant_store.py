import uuid
from collections.abc import Iterable
from typing import Any

from qdrant_client import QdrantClient, models

from app.core.config import Settings
from app.llm.client import ProviderConfigurationError, ProviderRequestError
from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.schemas.chat import Confidence


class QdrantKnowledgeStore:
    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        collection_name: str,
        client: Any | None = None,
    ) -> None:
        if not url and client is None:
            raise ProviderConfigurationError("Qdrant URL is not configured.")
        if not collection_name:
            raise ProviderConfigurationError("Qdrant collection is not configured.")

        self._client = client or QdrantClient(url=url, api_key=api_key or None)
        self._collection_name = collection_name

    @classmethod
    def from_settings(cls, settings: Settings) -> "QdrantKnowledgeStore":
        return cls(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection_name=settings.qdrant_collection,
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
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
            self._ensure_payload_indexes()
        except Exception as exc:
            raise ProviderRequestError("Qdrant collection setup failed.") from exc

    def _ensure_payload_indexes(self) -> None:
        try:
            self._client.create_payload_index(
                collection_name=self._collection_name,
                field_name="source",
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
        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must have the same length.")

        self.ensure_collection(vector_size=vector_size)
        self.delete_sources(source_files)
        if chunks:
            self.upsert_chunks(chunks=chunks, embeddings=embeddings)

    def delete_sources(self, source_files: Iterable[str]) -> None:
        try:
            for source_file in source_files:
                self._client.delete(
                    collection_name=self._collection_name,
                    points_selector=models.FilterSelector(
                        filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="source",
                                    match=models.MatchValue(value=source_file),
                                )
                            ]
                        )
                    ),
                )
        except Exception as exc:
            raise ProviderRequestError("Qdrant source cleanup failed.") from exc

    def upsert_chunks(self, *, chunks: list[KnowledgeChunk], embeddings: list[list[float]]) -> None:
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
            raise ProviderRequestError("Qdrant upsert failed.") from exc

    def search(
        self,
        *,
        embedding: list[float],
        limit: int,
        score_threshold: float,
    ) -> list[KnowledgeChunk]:
        if not embedding:
            return []

        try:
            query_response = self._client.query_points(
                collection_name=self._collection_name,
                query=embedding,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )
        except Exception as exc:
            raise ProviderRequestError("Qdrant search failed.") from exc

        points = getattr(query_response, "points", query_response)
        return [_chunk_from_point(point) for point in points]


def _point_id(chunk: KnowledgeChunk) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"alextym:{chunk.id}"))


def _payload_from_chunk(chunk: KnowledgeChunk) -> dict[str, Any]:
    return {
        "chunk_id": chunk.id,
        "content": chunk.content,
        "source": chunk.metadata.source,
        "section": chunk.metadata.section,
        "topic": chunk.metadata.topic,
        "visibility": chunk.metadata.visibility,
        "confidence": chunk.metadata.confidence,
        "source_confidence": chunk.metadata.source_confidence,
        "tags": list(chunk.metadata.tags),
    }


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
        ),
    )


def _source_confidence(value: object) -> Confidence:
    return value if value in {"low", "medium", "high"} else "medium"
