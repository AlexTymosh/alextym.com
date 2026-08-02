from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from app.rag.case_study_rag_source import (
    CaseStudyChunkPayload,
    CaseStudyRagChunk,
    CaseStudyRagDocument,
    CaseStudySourceReference,
    load_case_study_rag_document,
)
from app.rag.public_knowledge_rag_source import (
    build_public_knowledge_rag_document,
    load_public_knowledge_rag_document,
    main,
    render_public_knowledge_rag_json,
    write_public_knowledge_rag_outputs,
)
from app.rag.resume_rag_source import (
    ChunkPayload,
    ResumeRagChunk,
    ResumeRagDocument,
    SourceReference,
    build_resume_rag_document,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RESUME_PATH = REPOSITORY_ROOT / "content" / "public" / "resume.md"
CASE_STUDIES_DIRECTORY = REPOSITORY_ROOT / "content" / "public" / "case-studies"


def test_combines_resume_first_without_changing_chunk_shape() -> None:
    resume_chunk = _resume_chunk()
    case_chunk = _case_chunk()

    document = build_public_knowledge_rag_document(
        ResumeRagDocument(
            source_path="content/public/resume.md",
            chunks=(resume_chunk,),
        ),
        CaseStudyRagDocument(
            source_directory="content/public/case-studies",
            resume_path="content/public/resume.md",
            chunks=(case_chunk,),
        ),
    )

    assert document.chunks == (asdict(resume_chunk), asdict(case_chunk))
    assert document.source_files == (
        "content/public/resume.md",
        "content/public/case-studies/sample.case.md",
    )
    assert [(group.id, group.chunk_count) for group in document.source_groups] == [
        ("resume", 1),
        ("case-studies", 1),
    ]


def test_rendered_json_is_schema_compatible_and_deterministic() -> None:
    document = build_public_knowledge_rag_document(
        ResumeRagDocument(
            source_path="content/public/resume.md",
            chunks=(_resume_chunk(),),
        ),
        CaseStudyRagDocument(
            source_directory="content/public/case-studies",
            resume_path="content/public/resume.md",
            chunks=(_case_chunk(),),
        ),
    )

    first = render_public_knowledge_rag_json(document)
    second = render_public_knowledge_rag_json(document)
    payload = json.loads(first)

    assert first == second
    assert payload["schema_version"] == 2
    assert payload["purpose"] == "public_knowledge_rag_extraction"
    assert [chunk["id"] for chunk in payload["chunks"]] == [
        "resume:summary:rag",
        "case:case-sample:analysis",
    ]
    assert payload["chunks"][0] == json.loads(json.dumps(asdict(_resume_chunk())))


def test_rejects_duplicate_ids_across_source_groups() -> None:
    duplicate_case_chunk = _case_chunk(chunk_id="resume:summary:rag")

    with pytest.raises(ValueError, match="chunk IDs must be unique"):
        build_public_knowledge_rag_document(
            ResumeRagDocument(
                source_path="content/public/resume.md",
                chunks=(_resume_chunk(),),
            ),
            CaseStudyRagDocument(
                source_directory="content/public/case-studies",
                resume_path="content/public/resume.md",
                chunks=(duplicate_case_chunk,),
            ),
        )


def test_repository_sources_build_one_complete_public_knowledge_document() -> None:
    resume_document = build_resume_rag_document(
        RESUME_PATH.read_text(encoding="utf-8"),
        source_path="content/public/resume.md",
    )
    case_study_document = load_case_study_rag_document(
        case_studies_directory=CASE_STUDIES_DIRECTORY,
        resume_path=RESUME_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    document = load_public_knowledge_rag_document(
        resume_path=RESUME_PATH,
        case_studies_directory=CASE_STUDIES_DIRECTORY,
        repository_root=REPOSITORY_ROOT,
    )

    group_counts = {group.id: group.chunk_count for group in document.source_groups}
    chunk_ids = {chunk["id"] for chunk in document.chunks}

    assert group_counts == {
        "resume": len(resume_document.chunks),
        "case-studies": len(case_study_document.chunks),
    }
    assert len(document.chunks) == len(resume_document.chunks) + len(case_study_document.chunks)
    assert len(document.source_files) == 1 + len(
        {chunk.source.path for chunk in case_study_document.chunks}
    )
    assert "resume:summary:rag" in chunk_ids
    assert "case:case-weee-reporting-automation:limitations" in chunk_ids


def test_repeated_output_generation_is_byte_identical(tmp_path: Path) -> None:
    first_json = tmp_path / "first" / "public-knowledge.json"
    first_preview = tmp_path / "first" / "preview.md"
    second_json = tmp_path / "second" / "public-knowledge.json"
    second_preview = tmp_path / "second" / "preview.md"

    first_document = write_public_knowledge_rag_outputs(
        resume_path=RESUME_PATH,
        case_studies_directory=CASE_STUDIES_DIRECTORY,
        json_output_path=first_json,
        preview_output_path=first_preview,
        repository_root=REPOSITORY_ROOT,
    )
    second_document = write_public_knowledge_rag_outputs(
        resume_path=RESUME_PATH,
        case_studies_directory=CASE_STUDIES_DIRECTORY,
        json_output_path=second_json,
        preview_output_path=second_preview,
        repository_root=REPOSITORY_ROOT,
    )

    assert len(first_document.chunks) == len(second_document.chunks)
    assert first_document.chunks
    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_preview.read_bytes() == second_preview.read_bytes()


def test_main_prints_readable_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    json_output = tmp_path / "public-knowledge.json"
    preview_output = tmp_path / "preview.md"
    monkeypatch.setenv("NO_COLOR", "1")

    main(
        [
            "--resume",
            str(RESUME_PATH),
            "--case-studies",
            str(CASE_STUDIES_DIRECTORY),
            "--json-output",
            str(json_output),
            "--preview-output",
            str(preview_output),
        ]
    )

    output = capsys.readouterr().out
    assert "[OK] Extracted" in output
    assert "public-knowledge chunk(s)" in output
    assert "resume=" in output
    assert "case-studies=" in output
    assert json_output.exists()
    assert preview_output.exists()


def _resume_chunk() -> ResumeRagChunk:
    source = SourceReference(
        path="content/public/resume.md",
        id="summary",
        title="Summary",
        title_url=None,
        section="summary",
    )
    payload = ChunkPayload(
        topic="summary",
        visibility="public",
        confidence="self-reported",
        source_confidence="medium",
        primary_tags=("automation",),
        secondary_tags=("api",),
        tags=("api", "automation"),
    )
    return ResumeRagChunk(
        id="resume:summary:rag",
        parent_id="resume:summary",
        source=source,
        payload=payload,
        answer_facts=("The Owner builds automation systems.",),
        retrieval_hints=("Useful for profile questions.",),
        content="- The Owner builds automation systems.",
        vector_inputs=_vector_inputs("Summary"),
        retrieval={"modes": ("dense",), "parent_id": "resume:summary"},
    )


def _case_chunk(*, chunk_id: str = "case:case-sample:analysis") -> CaseStudyRagChunk:
    source = CaseStudySourceReference(
        path="content/public/case-studies/sample.case.md",
        id="case-sample",
        title="Sample Case",
        section="experience",
        organization="Example Ltd",
        date="2026-01",
        parent_entry_id="sample-entry",
        case_section="analysis",
        case_section_title="Analysis",
    )
    payload = CaseStudyChunkPayload(
        topic="sample-analysis",
        visibility="public",
        confidence="self-reported",
        source_confidence="medium",
        document_type="case-study",
        source_group="case-studies",
        case_id="case-sample",
        case_section="analysis",
        parent_entry_id="sample-entry",
        retrieval_priority="normal",
        primary_tags=("case-study",),
        secondary_tags=("analysis",),
        tags=("analysis", "case-study"),
    )
    return CaseStudyRagChunk(
        id=chunk_id,
        parent_id="case:case-sample",
        source=source,
        payload=payload,
        answer_facts=("The Owner analysed the process.",),
        retrieval_hints=("Useful for analysis questions.",),
        content="- The Owner analysed the process.",
        vector_inputs=_vector_inputs("Sample Case — Analysis"),
        retrieval={"modes": ("dense",), "parent_id": "case:case-sample"},
    )


def _vector_inputs(title: str) -> dict[str, str]:
    return {
        "title_dense": title,
        "body_dense": f"{title}\n\nBody",
        "summary_dense": f"{title}\n\nSummary",
        "keywords_sparse": "automation analysis",
        "rerank_text": f"{title}\n\nRerank",
        "compression_text": "- Content",
    }
