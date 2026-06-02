import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.rag.structured_knowledge import GENERATED_RESUME_CHUNKS_FILE
from app.rag.structured_knowledge import LEGACY_RESUME_SOURCE_FILE
from app.rag.structured_knowledge import load_generated_resume_chunks
from scripts.ingest_generated_resume_chunks import ingest_generated_resume_chunks


def test_load_generated_resume_chunks_uses_body_dense_for_embedding(
    tmp_path: Path,
) -> None:
    chunks_path = _write_generated_chunks(tmp_path)

    bundle = load_generated_resume_chunks(chunks_path)

    assert len(bundle.chunks) == 1
    assert bundle.embedding_texts == ["Body dense text for embeddings."]
    assert bundle.source_files == (
        LEGACY_RESUME_SOURCE_FILE,
        GENERATED_RESUME_CHUNKS_FILE,
    )
    assert bundle.chunks[0].content == "- Alex answer fact."
    assert bundle.chunks[0].metadata.source == "Hard Skills"
    assert bundle.chunks[0].metadata.section == "experience"
    assert bundle.chunks[0].metadata.topic == "hard-skills"
    assert bundle.chunks[0].metadata.tags == ("api", "automation")
    assert bundle.chunks[0].metadata.extra["source_file"] == (GENERATED_RESUME_CHUNKS_FILE)


def test_load_generated_resume_chunks_rejects_unsupported_schema(
    tmp_path: Path,
) -> None:
    chunks_path = _write_generated_chunks(tmp_path, schema_version=999)

    with pytest.raises(ValueError, match="Unsupported generated RAG schema"):
        load_generated_resume_chunks(chunks_path)


def test_ingest_generated_resume_chunks_uses_structured_json(
    tmp_path: Path,
) -> None:
    chunks_path = _write_generated_chunks(tmp_path)
    fake_embedding_client = FakeEmbeddingClient()
    fake_vector_store = FakeVectorStore()

    summary = ingest_generated_resume_chunks(
        settings=_settings(),
        chunks_path=chunks_path,
        embedding_client=fake_embedding_client,
        vector_store=fake_vector_store,
    )

    assert summary.loaded_chunks == 1
    assert summary.indexed_chunks == 1
    assert fake_embedding_client.texts == ["Body dense text for embeddings."]
    assert fake_vector_store.source_files == (
        LEGACY_RESUME_SOURCE_FILE,
        GENERATED_RESUME_CHUNKS_FILE,
    )
    assert fake_vector_store.replaced_chunks[0].metadata.extra["parent_id"] == (
        "resume:hard-skills"
    )
    assert (
        fake_vector_store.replaced_chunks[0].metadata.extra["vector_inputs"]["body_dense"]
        == "Body dense text for embeddings."
    )


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.texts = texts
        return [[1.0, 0.0] for _ in texts]


class FakeVectorStore:
    def __init__(self) -> None:
        self.replaced_chunks = []
        self.replaced_embeddings: list[list[float]] = []
        self.source_files: tuple[str, ...] = ()
        self.vector_size = 0

    def replace_source_chunks(
        self,
        *,
        chunks: list[object],
        embeddings: list[list[float]],
        source_files: tuple[str, ...],
        vector_size: int,
    ) -> None:
        self.replaced_chunks = chunks
        self.replaced_embeddings = embeddings
        self.source_files = source_files
        self.vector_size = vector_size


def _write_generated_chunks(
    tmp_path: Path,
    *,
    schema_version: int = 2,
) -> Path:
    chunks_path = tmp_path / GENERATED_RESUME_CHUNKS_FILE
    chunks_path.write_text(
        json.dumps(
            {
                "schema_version": schema_version,
                "source_path": "frontend/content/resume.md",
                "purpose": "resume_rag_extraction",
                "chunks": [_generated_chunk()],
            }
        ),
        encoding="utf-8",
    )
    return chunks_path


def _generated_chunk() -> dict[str, object]:
    return {
        "id": "resume:hard-skills:rag",
        "parent_id": "resume:hard-skills",
        "source": {
            "path": "frontend/content/resume.md",
            "id": "hard-skills",
            "title": "Hard Skills",
            "title_url": None,
            "section": "experience",
        },
        "payload": {
            "topic": "hard-skills",
            "visibility": "public",
            "confidence": "self-reported",
            "source_confidence": "medium",
            "primary_tags": ["automation"],
            "secondary_tags": ["api"],
            "tags": ["api", "automation"],
        },
        "answer_facts": ["Alex answer fact."],
        "retrieval_hints": ["Search hint."],
        "content": "- Alex answer fact.",
        "vector_inputs": {
            "title_dense": "Hard Skills",
            "body_dense": "Body dense text for embeddings.",
            "summary_dense": "Summary dense text.",
            "keywords_sparse": "automation api",
            "rerank_text": "Rerank text.",
            "compression_text": "- Alex answer fact.",
        },
        "retrieval": {
            "modes": ["dense"],
            "named_vectors": ["body_dense"],
            "parent_id": "resume:hard-skills",
            "payload_filter_fields": ["payload.topic"],
        },
    }


def _settings() -> Settings:
    return Settings(
        app_name="alextym API",
        environment="test",
        frontend_origin="http://localhost:3000",
        openai_api_key="test-key",
        openai_model="gpt-5-mini",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_dimensions=2,
        openai_max_output_tokens=300,
        openai_reasoning_effort="low",
        qdrant_url="http://qdrant.test",
        qdrant_api_key="",
        qdrant_collection="alex_public_knowledge",
        rag_top_k=6,
        rag_score_threshold=0.72,
        resend_api_key="",
        contact_target_email="",
        contact_from_email="",
        rate_limiting_enabled=True,
        chat_daily_limit_per_ip=50,
        contact_daily_limit_per_ip=5,
    )
