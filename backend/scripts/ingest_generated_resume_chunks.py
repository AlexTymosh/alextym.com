from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.llm.client import EmbeddingClient, ProviderConfigurationError
from app.llm.client import ProviderRequestError
from app.llm.openai_client import OpenAIEmbeddingClient
from app.rag.qdrant_store import QdrantKnowledgeStore
from app.rag.structured_knowledge import GeneratedResumeChunkBundle
from app.rag.structured_knowledge import load_generated_resume_chunks


@dataclass(frozen=True)
class GeneratedIngestionSummary:
    source_files: tuple[str, ...]
    loaded_chunks: int
    indexed_chunks: int


def ingest_generated_resume_chunks(
    *,
    settings: Settings | None = None,
    chunks_path: Path | None = None,
    embedding_client: EmbeddingClient | None = None,
    vector_store: QdrantKnowledgeStore | None = None,
) -> GeneratedIngestionSummary:
    resolved_settings = settings or get_settings()
    bundle = load_generated_resume_chunks(chunks_path)
    resolved_store = vector_store or QdrantKnowledgeStore.from_settings(resolved_settings)
    embeddings = _embed_bundle(
        bundle=bundle,
        embedding_client=embedding_client or OpenAIEmbeddingClient.from_settings(resolved_settings),
    )

    resolved_store.replace_source_chunks(
        chunks=bundle.chunks,
        embeddings=embeddings,
        source_files=bundle.source_files,
        vector_size=resolved_settings.openai_embedding_dimensions,
    )

    return GeneratedIngestionSummary(
        source_files=bundle.source_files,
        loaded_chunks=len(bundle.chunks),
        indexed_chunks=len(embeddings),
    )


def main() -> None:
    try:
        summary = ingest_generated_resume_chunks()
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"Generated RAG ingestion failed: {exc}") from exc
    except (ProviderConfigurationError, ProviderRequestError) as exc:
        raise SystemExit(f"Generated RAG ingestion failed: {exc}") from exc

    print(
        "Indexed "
        f"{summary.indexed_chunks} generated RAG chunk(s) from "
        f"{', '.join(summary.source_files)} "
        f"({summary.loaded_chunks} loaded)."
    )


def _embed_bundle(
    *,
    bundle: GeneratedResumeChunkBundle,
    embedding_client: EmbeddingClient,
) -> list[list[float]]:
    if not bundle.embedding_texts:
        return []

    return embedding_client.embed_texts(bundle.embedding_texts)


if __name__ == "__main__":
    main()
