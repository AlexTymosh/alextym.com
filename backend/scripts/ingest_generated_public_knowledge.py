from app.llm.client import ProviderConfigurationError, ProviderRequestError
from app.rag.generated_ingestion import ingest_generated_knowledge_chunks


def main() -> None:
    try:
        summary = ingest_generated_knowledge_chunks()
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"Public-knowledge ingestion failed: {exc}") from exc
    except (ProviderConfigurationError, ProviderRequestError) as exc:
        raise SystemExit(f"Public-knowledge ingestion failed: {exc}") from exc

    print(
        "Indexed "
        f"{summary.indexed_chunks} public-knowledge chunk(s) from "
        f"{', '.join(summary.source_groups)} "
        f"with dataset version {summary.dataset_version} "
        f"({summary.loaded_chunks} loaded)."
    )


if __name__ == "__main__":
    main()
