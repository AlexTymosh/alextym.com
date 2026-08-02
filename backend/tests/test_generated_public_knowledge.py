import json
from pathlib import Path

import pytest

from app.rag.structured_knowledge import (
    GENERATED_CASE_STUDY_CHUNKS_FILE,
    GENERATED_PUBLIC_KNOWLEDGE_CHUNKS_FILE,
    GENERATED_RESUME_CHUNKS_FILE,
    load_generated_knowledge_chunks,
    load_generated_resume_chunks,
)


def test_load_generated_knowledge_chunks_combines_source_types(tmp_path: Path) -> None:
    chunks_path = _write_public_knowledge(tmp_path)

    bundle = load_generated_knowledge_chunks(chunks_path)

    assert [chunk.id for chunk in bundle.chunks] == [
        "resume:summary:rag",
        "case:case-sample:analysis",
    ]
    assert bundle.embedding_texts == ["Resume body dense.", "Case body dense."]
    assert bundle.source_files == (
        "content/public/resume.md",
        "content/public/case-studies/sample.case.md",
        GENERATED_PUBLIC_KNOWLEDGE_CHUNKS_FILE,
        GENERATED_RESUME_CHUNKS_FILE,
        GENERATED_CASE_STUDY_CHUNKS_FILE,
    )
    case_chunk = bundle.chunks[1]
    assert case_chunk.metadata.extra["source_file"] == (
        "content/public/case-studies/sample.case.md"
    )
    assert case_chunk.metadata.extra["payload"]["case_id"] == "case-sample"
    assert case_chunk.metadata.extra["payload"]["source_group"] == "case-studies"


def test_load_generated_knowledge_chunks_rejects_duplicate_chunk_ids(
    tmp_path: Path,
) -> None:
    chunks_path = _write_public_knowledge(tmp_path, duplicate_id=True)

    with pytest.raises(ValueError, match="Duplicate generated RAG chunk id"):
        load_generated_knowledge_chunks(chunks_path)


def test_load_generated_knowledge_chunks_requires_valid_source_files(
    tmp_path: Path,
) -> None:
    chunks_path = _write_public_knowledge(tmp_path)
    payload = json.loads(chunks_path.read_text(encoding="utf-8"))
    payload["source_files"] = ["content/public/resume.md", ""]
    chunks_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="source_files"):
        load_generated_knowledge_chunks(chunks_path)


def test_legacy_resume_loader_remains_compatible(tmp_path: Path) -> None:
    chunks_path = tmp_path / GENERATED_RESUME_CHUNKS_FILE
    chunks_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source_path": "content/public/resume.md",
                "purpose": "resume_rag_extraction",
                "chunks": [_chunk("resume:summary:rag", "Resume body dense.")],
            }
        ),
        encoding="utf-8",
    )

    bundle = load_generated_resume_chunks(chunks_path)

    assert len(bundle.chunks) == 1
    assert bundle.embedding_texts == ["Resume body dense."]
    assert bundle.source_files == (
        "content/public/resume.md",
        GENERATED_RESUME_CHUNKS_FILE,
    )


def _write_public_knowledge(
    tmp_path: Path,
    *,
    duplicate_id: bool = False,
) -> Path:
    chunks_path = tmp_path / GENERATED_PUBLIC_KNOWLEDGE_CHUNKS_FILE
    case_id = "resume:summary:rag" if duplicate_id else "case:case-sample:analysis"
    chunks_path.write_text(
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
                    _chunk("resume:summary:rag", "Resume body dense."),
                    _chunk(
                        case_id,
                        "Case body dense.",
                        source_path="content/public/case-studies/sample.case.md",
                        source_title="Sample Case",
                        source_section="experience",
                        payload={
                            "topic": "sample-analysis",
                            "visibility": "public",
                            "confidence": "self-reported",
                            "source_confidence": "medium",
                            "document_type": "case-study",
                            "source_group": "case-studies",
                            "case_id": "case-sample",
                            "case_section": "analysis",
                            "tags": ["analysis", "case-study"],
                        },
                    ),
                ],
            }
        ),
        encoding="utf-8",
    )
    return chunks_path


def _chunk(
    chunk_id: str,
    body_dense: str,
    *,
    source_path: str = "content/public/resume.md",
    source_title: str = "Summary",
    source_section: str = "summary",
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    resolved_payload = payload or {
        "topic": "summary",
        "visibility": "public",
        "confidence": "self-reported",
        "source_confidence": "medium",
        "tags": ["automation"],
    }
    return {
        "id": chunk_id,
        "parent_id": chunk_id.rsplit(":", 1)[0],
        "source": {
            "path": source_path,
            "id": "source-id",
            "title": source_title,
            "section": source_section,
        },
        "payload": resolved_payload,
        "answer_facts": ["The Owner has a documented fact."],
        "retrieval_hints": ["Useful for relevant questions."],
        "content": "- The Owner has a documented fact.",
        "vector_inputs": {
            "title_dense": source_title,
            "body_dense": body_dense,
            "summary_dense": f"{source_title} summary.",
            "keywords_sparse": "automation",
            "rerank_text": body_dense,
            "compression_text": "- The Owner has a documented fact.",
        },
        "retrieval": {"modes": ["dense"]},
    }
