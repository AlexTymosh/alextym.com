import hashlib
import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.rag.generated_ingestion import ingest_generated_knowledge_chunks


def test_ingest_generated_knowledge_uses_versioned_single_vector_replace(
    tmp_path: Path,
) -> None:
    chunks_path = _write_public_knowledge(tmp_path)
    embedding_client = FakeEmbeddingClient()
    vector_store = FakeVersionedStore()

    summary = ingest_generated_knowledge_chunks(
        settings=_settings(),
        chunks_path=chunks_path,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )

    expected_version = hashlib.sha256(chunks_path.read_bytes()).hexdigest()
    assert summary.loaded_chunks == 2
    assert summary.indexed_chunks == 2
    assert summary.source_groups == ("resume", "case-studies")
    assert summary.dataset_version == expected_version
    assert embedding_client.text_batches == [["Resume body.", "Case body."]]
    assert vector_store.single_call is not None
    assert vector_store.single_call["source_groups"] == ("resume", "case-studies")
    assert vector_store.single_call["dataset_version"] == expected_version
    assert len(vector_store.single_call["chunks"]) == 2
    assert all(
        chunk.metadata.extra["dataset_version"] == expected_version
        for chunk in vector_store.single_call["chunks"]
    )


def test_ingest_generated_knowledge_uses_versioned_named_vector_replace(
    tmp_path: Path,
) -> None:
    chunks_path = _write_public_knowledge(tmp_path)
    embedding_client = FakeEmbeddingClient()
    vector_store = FakeVersionedStore()

    summary = ingest_generated_knowledge_chunks(
        settings=_settings(qdrant_vector_mode="named"),
        chunks_path=chunks_path,
        embedding_client=embedding_client,
        vector_store=vector_store,
    )

    assert summary.indexed_chunks == 2
    assert embedding_client.text_batches == [
        ["Resume", "Case — Analysis"],
        ["Resume body.", "Case body."],
        ["Resume summary.", "Case summary."],
    ]
    assert vector_store.named_call is not None
    assert set(vector_store.named_call["named_embeddings"][0]) == {
        "title_dense",
        "body_dense",
        "summary_dense",
    }


def test_embedding_failure_happens_before_any_qdrant_write(tmp_path: Path) -> None:
    chunks_path = _write_public_knowledge(tmp_path)
    vector_store = FakeVersionedStore()

    with pytest.raises(RuntimeError, match="embedding failure"):
        ingest_generated_knowledge_chunks(
            settings=_settings(),
            chunks_path=chunks_path,
            embedding_client=FailingEmbeddingClient(),
            vector_store=vector_store,
        )

    assert vector_store.single_call is None
    assert vector_store.named_call is None


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.text_batches: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.text_batches.append(texts)
        return [[float(index + 1), 0.0] for index in range(len(texts))]


class FailingEmbeddingClient:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding failure")


class FakeVersionedStore:
    def __init__(self) -> None:
        self.single_call: dict[str, object] | None = None
        self.named_call: dict[str, object] | None = None

    def replace_versioned_chunks(self, **kwargs: object) -> None:
        self.single_call = kwargs

    def replace_versioned_named_vector_chunks(self, **kwargs: object) -> None:
        self.named_call = kwargs


def _write_public_knowledge(tmp_path: Path) -> Path:
    path = tmp_path / "public-knowledge.generated.chunks.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "purpose": "public_knowledge_rag_extraction",
                "source_files": [
                    "content/public/resume.md",
                    "content/public/case-studies/sample.case.md",
                ],
                "source_groups": [
                    {"id": "resume", "chunk_count": 1},
                    {"id": "case-studies", "chunk_count": 1},
                ],
                "chunks": [
                    _chunk(
                        "resume:summary:rag",
                        title="Resume",
                        body="Resume body.",
                        summary="Resume summary.",
                    ),
                    _chunk(
                        "case:case-sample:analysis",
                        title="Case — Analysis",
                        body="Case body.",
                        summary="Case summary.",
                        case=True,
                    ),
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _chunk(
    chunk_id: str,
    *,
    title: str,
    body: str,
    summary: str,
    case: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "topic": "analysis" if case else "summary",
        "visibility": "public",
        "confidence": "self-reported",
        "source_confidence": "medium",
        "tags": ["case-study"] if case else ["resume"],
    }
    source: dict[str, object] = {
        "path": (
            "content/public/case-studies/sample.case.md" if case else "content/public/resume.md"
        ),
        "id": "case-sample" if case else "summary",
        "title": "Sample Case" if case else "Summary",
        "section": "experience" if case else "summary",
    }
    if case:
        payload.update(
            {
                "document_type": "case-study",
                "source_group": "case-studies",
                "case_id": "case-sample",
                "case_section": "analysis",
            }
        )
        source["organization"] = "Example Ltd"

    return {
        "id": chunk_id,
        "parent_id": chunk_id.rsplit(":", 1)[0],
        "source": source,
        "payload": payload,
        "answer_facts": [body],
        "retrieval_hints": [],
        "content": f"- {body}",
        "vector_inputs": {
            "title_dense": title,
            "body_dense": body,
            "summary_dense": summary,
            "keywords_sparse": "case-study" if case else "resume",
            "rerank_text": body,
            "compression_text": f"- {body}",
        },
        "retrieval": {"modes": ["dense"]},
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
        qdrant_collection="public_knowledge",
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
