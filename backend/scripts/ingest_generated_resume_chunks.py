from pathlib import Path

from app.core.config import Settings
from app.llm.client import EmbeddingClient, ProviderConfigurationError
from app.llm.client import ProviderRequestError
from app.rag.generated_ingestion import GeneratedIngestionSummary
from app.rag.generated_ingestion import ingest_generated_resume_chunks_legacy
from app.rag.qdrant_store import QdrantKnowledgeStore


def ingest_generated_resume_chunks(
    *,
    settings: Settings | None = None,
    chunks_path: Path | None = None,
    embedding_client: EmbeddingClient | None = None,
    vector_store: QdrantKnowledgeStore | None = None,
) -> GeneratedIngestionSummary:
    return ingest_generated_resume_chunks_legacy(
        settings=settings,
        chunks_path=chunks_path,
        embedding_client=embedding_client,
        vector_store=vector_store,
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


if __name__ == "__main__":
    main()
