from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.llm.client import EmbeddingClient
from app.llm.openai_client import OpenAIEmbeddingClient
from app.rag.qdrant_store import NamedEmbeddings, QdrantKnowledgeStore
from app.rag.structured_knowledge import GeneratedKnowledgeBundle
from app.rag.structured_knowledge import load_generated_knowledge_chunks
from app.rag.structured_knowledge import load_generated_resume_chunks
from app.rag.vector_config import NAMED_DENSE_VECTOR_NAMES


@dataclass(frozen=True)
class GeneratedIngestionSummary:
    source_files: tuple[str, ...]
    source_groups: tuple[str, ...]
    dataset_version: str
    loaded_chunks: int
    indexed_chunks: int


def ingest_generated_knowledge_chunks(
    *,
    settings: Settings | None = None,
    chunks_path: Path | None = None,
    embedding_client: EmbeddingClient | None = None,
    vector_store: QdrantKnowledgeStore | None = None,
) -> GeneratedIngestionSummary:
    resolved_settings = settings or get_settings()
    bundle = load_generated_knowledge_chunks(chunks_path)
    resolved_store = vector_store or QdrantKnowledgeStore.from_settings(resolved_settings)
    resolved_embedding_client = embedding_client or OpenAIEmbeddingClient.from_settings(
        resolved_settings
    )

    if resolved_settings.qdrant_vector_mode == "named":
        named_embeddings = _embed_named_bundle(
            bundle=bundle,
            embedding_client=resolved_embedding_client,
        )
        resolved_store.replace_versioned_named_vector_chunks(
            chunks=bundle.chunks,
            named_embeddings=named_embeddings,
            source_groups=bundle.source_groups,
            dataset_version=bundle.dataset_version,
            legacy_source_files=bundle.source_files,
            vector_size=resolved_settings.openai_embedding_dimensions,
        )
        indexed_chunks = len(named_embeddings)
    else:
        embeddings = _embed_bundle(
            bundle=bundle,
            embedding_client=resolved_embedding_client,
        )
        resolved_store.replace_versioned_chunks(
            chunks=bundle.chunks,
            embeddings=embeddings,
            source_groups=bundle.source_groups,
            dataset_version=bundle.dataset_version,
            legacy_source_files=bundle.source_files,
            vector_size=resolved_settings.openai_embedding_dimensions,
        )
        indexed_chunks = len(embeddings)

    return _summary(bundle, indexed_chunks=indexed_chunks)


def ingest_generated_resume_chunks_legacy(
    *,
    settings: Settings | None = None,
    chunks_path: Path | None = None,
    embedding_client: EmbeddingClient | None = None,
    vector_store: QdrantKnowledgeStore | None = None,
) -> GeneratedIngestionSummary:
    """Preserve the resume-only ingestion API during the staged migration."""

    resolved_settings = settings or get_settings()
    bundle = load_generated_resume_chunks(chunks_path)
    resolved_store = vector_store or QdrantKnowledgeStore.from_settings(resolved_settings)
    resolved_embedding_client = embedding_client or OpenAIEmbeddingClient.from_settings(
        resolved_settings
    )

    if resolved_settings.qdrant_vector_mode == "named":
        named_embeddings = _embed_named_bundle(
            bundle=bundle,
            embedding_client=resolved_embedding_client,
        )
        resolved_store.replace_source_named_vector_chunks(
            chunks=bundle.chunks,
            named_embeddings=named_embeddings,
            source_files=bundle.source_files,
            vector_size=resolved_settings.openai_embedding_dimensions,
        )
        indexed_chunks = len(named_embeddings)
    else:
        embeddings = _embed_bundle(
            bundle=bundle,
            embedding_client=resolved_embedding_client,
        )
        resolved_store.replace_source_chunks(
            chunks=bundle.chunks,
            embeddings=embeddings,
            source_files=bundle.source_files,
            vector_size=resolved_settings.openai_embedding_dimensions,
        )
        indexed_chunks = len(embeddings)

    return _summary(bundle, indexed_chunks=indexed_chunks)


def _summary(
    bundle: GeneratedKnowledgeBundle,
    *,
    indexed_chunks: int,
) -> GeneratedIngestionSummary:
    return GeneratedIngestionSummary(
        source_files=bundle.source_files,
        source_groups=bundle.source_groups,
        dataset_version=bundle.dataset_version,
        loaded_chunks=len(bundle.chunks),
        indexed_chunks=indexed_chunks,
    )


def _embed_bundle(
    *,
    bundle: GeneratedKnowledgeBundle,
    embedding_client: EmbeddingClient,
) -> list[list[float]]:
    if not bundle.embedding_texts:
        return []

    return embedding_client.embed_texts(bundle.embedding_texts)


def _embed_named_bundle(
    *,
    bundle: GeneratedKnowledgeBundle,
    embedding_client: EmbeddingClient,
) -> list[NamedEmbeddings]:
    if not bundle.chunks:
        return []

    texts_by_vector = {
        vector_name: [
            _vector_input_text(chunk.metadata.extra, vector_name) for chunk in bundle.chunks
        ]
        for vector_name in NAMED_DENSE_VECTOR_NAMES
    }
    embeddings_by_vector = {
        vector_name: embedding_client.embed_texts(texts)
        for vector_name, texts in texts_by_vector.items()
    }

    return [
        {
            vector_name: embeddings_by_vector[vector_name][chunk_index]
            for vector_name in NAMED_DENSE_VECTOR_NAMES
        }
        for chunk_index in range(len(bundle.chunks))
    ]


def _vector_input_text(extra: dict[str, Any], vector_name: str) -> str:
    vector_inputs = extra.get("vector_inputs")
    if not isinstance(vector_inputs, dict):
        raise ValueError("Generated RAG chunk is missing vector_inputs.")

    value = vector_inputs.get(vector_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Generated RAG chunk is missing {vector_name} text.")

    return value
