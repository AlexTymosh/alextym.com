import json
from pathlib import Path

from app.core.config import Settings
from scripts.ingest_generated_resume_chunks import ingest_generated_resume_chunks


def test_generated_ingestion_uses_named_vectors_when_enabled(
    tmp_path: Path,
) -> None:
    chunks_path = _write_generated_chunks(tmp_path)
    embedding_client = FakeEmbeddingClient()
    vector_store = FakeNamedVectorStore()

    summary = ingest_generated_resume_chunks(
        settings=_settings(qdrant_vector_mode="named"),
        chunks_path=chunks_path,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )

    assert summary.loaded_chunks == 1
    assert summary.indexed_chunks == 1
    assert embedding_client.text_batches == [
        ["Hard Skills"],
        ["Hard Skills\n\nAlex uses Python."],
        ["Summary text."],
    ]
    assert vector_store.named_embeddings == [
        {
            "title_dense": [0.1, 0.2],
            "body_dense": [0.3, 0.4],
            "summary_dense": [0.5, 0.6],
        }
    ]


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.text_batches: list[list[str]] = []
        self._embeddings = [
            [[0.1, 0.2]],
            [[0.3, 0.4]],
            [[0.5, 0.6]],
        ]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.text_batches.append(texts)
        return self._embeddings.pop(0)

    def embed_text(self, text: str) -> list[float]:
        return [0.3, 0.4]


class FakeNamedVectorStore:
    def __init__(self) -> None:
        self.named_embeddings: list[dict[str, list[float]]] = []

    def replace_source_named_vector_chunks(
        self,
        *,
        chunks: list[object],
        named_embeddings: list[dict[str, list[float]]],
        source_files: tuple[str, ...],
        vector_size: int,
    ) -> None:
        self.named_embeddings = named_embeddings


def _write_generated_chunks(tmp_path: Path) -> Path:
    chunks_path = tmp_path / "resume.generated.chunks.json"
    chunks_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source_path": "content/public/resume.md",
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
            "path": "content/public/resume.md",
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
            "primary_tags": ["hard-skills"],
            "secondary_tags": ["python"],
            "tags": ["hard-skills", "python"],
        },
        "answer_facts": ["Alex uses Python."],
        "retrieval_hints": ["Useful for skill questions."],
        "content": "- Alex uses Python.",
        "vector_inputs": {
            "title_dense": "Hard Skills",
            "body_dense": "Hard Skills\n\nAlex uses Python.",
            "summary_dense": "Summary text.",
            "keywords_sparse": "hard-skills python",
            "rerank_text": "Hard Skills\n\nAlex uses Python.",
            "compression_text": "- Alex uses Python.",
        },
        "retrieval": {
            "modes": ["dense"],
            "named_vectors": ["title_dense", "body_dense", "summary_dense"],
            "parent_id": "resume:hard-skills",
            "payload_filter_fields": ["topic"],
        },
    }


def _settings(*, qdrant_vector_mode: str = "single") -> Settings:
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
        qdrant_collection="alex_public_knowledge_named",
        rag_top_k=6,
        rag_score_threshold=0.72,
        resend_api_key="",
        contact_target_email="",
        contact_from_email="",
        rate_limiting_enabled=True,
        chat_daily_limit_per_ip=50,
        contact_daily_limit_per_ip=5,
        qdrant_vector_mode=qdrant_vector_mode,
    )
