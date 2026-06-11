"""Legacy ingestion compatibility entrypoint.

Prefer `task rag:ingest:generated`, which extracts structured RAG chunks from
the canonical `content/public/resume.md` source before embedding.
"""

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.llm.client import EmbeddingClient, ProviderConfigurationError, ProviderRequestError
from app.llm.openai_client import OpenAIEmbeddingClient
from app.rag.knowledge_base import CANONICAL_RESUME_SOURCE_PATH, load_public_knowledge
from app.rag.models import KnowledgeChunk
from app.rag.qdrant_store import QdrantKnowledgeStore
from app.rag.structured_knowledge import GENERATED_RESUME_CHUNKS_FILE
from app.rag.structured_knowledge import LEGACY_RESUME_SOURCE_FILE
from app.rag.structured_knowledge import PREVIOUS_CANONICAL_RESUME_SOURCE_FILE


@dataclass(frozen=True)
class IngestionSummary:
    source_files: tuple[str, ...]
    loaded_chunks: int
    indexed_chunks: int


def ingest_public_knowledge(
    *,
    settings: Settings | None = None,
    knowledge_dir: Path | None = None,
    embedding_client: EmbeddingClient | None = None,
    vector_store: QdrantKnowledgeStore | None = None,
) -> IngestionSummary:
    resolved_settings = settings or get_settings()
    chunks = load_public_knowledge(knowledge_dir)
    source_files = (
        CANONICAL_RESUME_SOURCE_PATH.as_posix(),
        PREVIOUS_CANONICAL_RESUME_SOURCE_FILE,
        LEGACY_RESUME_SOURCE_FILE,
        GENERATED_RESUME_CHUNKS_FILE,
    )

    resolved_store = vector_store or QdrantKnowledgeStore.from_settings(resolved_settings)
    embeddings = (
        _embed_chunks(
            chunks=chunks,
            embedding_client=embedding_client
            or OpenAIEmbeddingClient.from_settings(resolved_settings),
        )
        if chunks
        else []
    )

    resolved_store.replace_source_chunks(
        chunks=chunks,
        embeddings=embeddings,
        source_files=source_files,
        vector_size=resolved_settings.openai_embedding_dimensions,
    )

    return IngestionSummary(
        source_files=source_files,
        loaded_chunks=len(chunks),
        indexed_chunks=len(embeddings),
    )


def main() -> None:
    try:
        summary = ingest_public_knowledge()
    except (ProviderConfigurationError, ProviderRequestError) as exc:
        raise SystemExit(f"Ingestion failed: {exc}") from exc

    print(
        "Indexed "
        f"{summary.indexed_chunks} chunk(s) from {', '.join(summary.source_files)} "
        f"({summary.loaded_chunks} loaded)."
    )


def _embed_chunks(
    *,
    chunks: list[KnowledgeChunk],
    embedding_client: EmbeddingClient,
) -> list[list[float]]:
    if not chunks:
        return []
    return embedding_client.embed_texts([chunk.content for chunk in chunks])


if __name__ == "__main__":
    main()
