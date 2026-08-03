from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.rag.case_study_contract import (
    CaseStudyCollection,
    parse_case_study_markdown,
    parse_resume_entries,
    validate_case_study_collection,
)
from app.rag.case_study_rag_source import (
    build_case_study_rag_document,
    load_case_study_rag_document,
    main,
    render_case_study_rag_json,
    render_case_study_rag_preview,
    write_case_study_rag_outputs,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASE_STUDIES_DIRECTORY = REPOSITORY_ROOT / "content" / "public" / "case-studies"
RESUME_PATH = REPOSITORY_ROOT / "content" / "public" / "resume.md"


def test_builds_one_answer_chunk_per_non_retrieval_section(tmp_path: Path) -> None:
    generated = _build_fixture_document(tmp_path)

    assert [chunk.payload.case_section for chunk in generated.chunks] == [
        "overview",
        "problem",
        "analysis",
        "results",
        "limitations",
    ]
    assert all(chunk.payload.case_section != "retrieval" for chunk in generated.chunks)


def test_uses_stable_case_and_section_ids(tmp_path: Path) -> None:
    generated = _build_fixture_document(tmp_path)

    assert [chunk.id for chunk in generated.chunks] == [
        "case:case-sample-automation:overview",
        "case:case-sample-automation:problem",
        "case:case-sample-automation:analysis",
        "case:case-sample-automation:results",
        "case:case-sample-automation:limitations",
    ]
    assert {chunk.parent_id for chunk in generated.chunks} == {"case:case-sample-automation"}


def test_preserves_source_and_retrieval_metadata(tmp_path: Path) -> None:
    chunk = _build_fixture_document(tmp_path).chunks[0]

    assert chunk.source.path == "content/public/case-studies/sample.case.md"
    assert chunk.source.title == "Sample Automation"
    assert chunk.source.organization == "Example Organisation"
    assert chunk.source.location == "United Kingdom"
    assert chunk.source.date == "2025-06"
    assert chunk.source.section == "experience"
    assert chunk.source.parent_entry_id == "sample-role"
    assert chunk.payload.document_type == "case-study"
    assert chunk.payload.source_group == "case-studies"
    assert chunk.payload.retrieval_priority == "high"
    assert chunk.payload.primary_tags == ("case-study", "automation")
    assert chunk.payload.secondary_tags == ("validation",)


def test_retrieval_metadata_does_not_leak_into_answer_content(tmp_path: Path) -> None:
    generated = _build_fixture_document(tmp_path)

    assert all("RETRIEVAL_ONLY_SENTINEL" not in chunk.content for chunk in generated.chunks)
    assert all(
        any("RETRIEVAL_ONLY_SENTINEL" in hint for hint in chunk.retrieval_hints)
        for chunk in generated.chunks
    )


def test_multiline_bullet_is_kept_as_one_logical_fact(tmp_path: Path) -> None:
    overview = _build_fixture_document(tmp_path).chunks[0]

    assert overview.answer_facts == (
        "The Owner built a controlled workflow and preserved this continuation "
        "inside the same logical bullet.",
    )
    assert overview.content.count("- ") == 1


def test_limitations_and_probability_language_are_preserved(tmp_path: Path) -> None:
    generated = _build_fixture_document(tmp_path)
    analysis = next(chunk for chunk in generated.chunks if chunk.payload.case_section == "analysis")
    limitations = next(
        chunk for chunk in generated.chunks if chunk.payload.case_section == "limitations"
    )

    assert "probable hardware issue remained unconfirmed" in analysis.content
    assert "could not prove the hardware cause" in limitations.content


def test_links_are_removed_from_embeddings_and_retained_as_references(
    tmp_path: Path,
) -> None:
    overview = _build_fixture_document(tmp_path).chunks[0]
    serialized_vectors = json.dumps(overview.vector_inputs, ensure_ascii=False)

    assert "controlled workflow" in overview.content
    assert "https://example.test/workflow(v2)" not in overview.content
    assert overview.source.links == ("https://example.test/workflow(v2)",)
    assert "](" not in serialized_vectors
    assert "https://" not in serialized_vectors


def test_vector_inputs_are_complete_and_retrieval_ready(tmp_path: Path) -> None:
    chunk = _build_fixture_document(tmp_path).chunks[0]

    assert set(chunk.vector_inputs) == {
        "title_dense",
        "body_dense",
        "summary_dense",
        "keywords_sparse",
        "rerank_text",
        "compression_text",
    }
    assert all(value.strip() for value in chunk.vector_inputs.values())
    assert "hybrid" in chunk.retrieval["modes"]
    assert "parent_child" in chunk.retrieval["modes"]
    assert "context_compression" in chunk.retrieval["modes"]


def test_json_generation_is_byte_deterministic(tmp_path: Path) -> None:
    generated = _build_fixture_document(tmp_path)

    first = render_case_study_rag_json(generated)
    second = render_case_study_rag_json(generated)

    assert first.encode("utf-8") == second.encode("utf-8")
    payload = json.loads(first)
    assert payload["schema_version"] == 2
    assert payload["purpose"] == "case_study_rag_extraction"


def test_preview_is_human_readable_not_an_embedding_source(tmp_path: Path) -> None:
    preview = render_case_study_rag_preview(_build_fixture_document(tmp_path))

    assert "human-readable preview" in preview
    assert "## Sample Automation — Overview" in preview
    assert "### Content" in preview
    assert "\n## Retrieval\n" not in preview


def test_write_outputs_is_repeatable_and_uses_lf_newlines(tmp_path: Path) -> None:
    case_directory, resume_path = _write_fixture_sources(tmp_path)
    json_output = tmp_path / ".tmp" / "rag" / "case-studies.generated.chunks.json"
    preview_output = tmp_path / ".tmp" / "preview" / "case-studies-rag-preview.md"

    first = write_case_study_rag_outputs(
        case_studies_directory=case_directory,
        resume_path=resume_path,
        json_output_path=json_output,
        preview_output_path=preview_output,
        repository_root=tmp_path,
    )
    first_json = json_output.read_bytes()
    first_preview = preview_output.read_bytes()

    second = write_case_study_rag_outputs(
        case_studies_directory=case_directory,
        resume_path=resume_path,
        json_output_path=json_output,
        preview_output_path=preview_output,
        repository_root=tmp_path,
    )

    assert first == second
    assert first_json == json_output.read_bytes()
    assert first_preview == preview_output.read_bytes()
    assert b"\r\n" not in first_json
    assert b"\r\n" not in first_preview


def test_main_prints_readable_no_colour_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case_directory, resume_path = _write_fixture_sources(tmp_path)
    json_output = tmp_path / ".tmp" / "rag" / "case-studies.json"
    preview_output = tmp_path / ".tmp" / "preview" / "case-studies.md"
    monkeypatch.setenv("NO_COLOR", "1")

    main(
        [
            "--case-studies",
            str(case_directory),
            "--resume",
            str(resume_path),
            "--json-output",
            str(json_output),
            "--preview-output",
            str(preview_output),
        ]
    )

    output = capsys.readouterr().out
    assert "\x1b[" not in output
    assert "[OK] Extracted 5 semantic chunk(s) from 1 case study source(s)." in output
    assert "[JSON]" in output
    assert "[PREVIEW]" in output
    assert "[NEXT]" in output


def test_repository_sources_generate_unique_chunks_for_all_ten_cases() -> None:
    generated = load_case_study_rag_document(
        case_studies_directory=CASE_STUDIES_DIRECTORY,
        resume_path=RESUME_PATH,
        repository_root=REPOSITORY_ROOT,
    )

    case_ids = {chunk.payload.case_id for chunk in generated.chunks}
    chunk_ids = [chunk.id for chunk in generated.chunks]

    assert len(case_ids) == 10
    assert len(chunk_ids) == len(set(chunk_ids))
    assert all(
        chunk.source.path.startswith("content/public/case-studies/") for chunk in generated.chunks
    )
    assert all(chunk.content.strip() for chunk in generated.chunks)
    assert all(
        value.strip() for chunk in generated.chunks for value in chunk.vector_inputs.values()
    )


def _build_fixture_document(tmp_path: Path):
    case_path = tmp_path / "content" / "public" / "case-studies" / "sample.case.md"
    resume_path = tmp_path / "content" / "public" / "resume.md"
    document = parse_case_study_markdown(_case_markdown(), source_path=case_path)
    resume_entries = parse_resume_entries(_resume_markdown(), source_path=resume_path)
    validate_case_study_collection((document,), resume_entries)
    collection = CaseStudyCollection(documents=(document,), resume_entries=resume_entries)

    return build_case_study_rag_document(
        collection,
        case_studies_directory=case_path.parent,
        resume_path=resume_path,
        repository_root=tmp_path,
    )


def _write_fixture_sources(tmp_path: Path) -> tuple[Path, Path]:
    case_directory = tmp_path / "content" / "public" / "case-studies"
    resume_path = tmp_path / "content" / "public" / "resume.md"
    case_directory.mkdir(parents=True)
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    (case_directory / "sample.case.md").write_text(_case_markdown(), encoding="utf-8", newline="\n")
    resume_path.write_text(_resume_markdown(), encoding="utf-8", newline="\n")
    return case_directory, resume_path


def _case_markdown() -> str:
    return """---
schemaVersion: 1
id: case-sample-automation
documentType: case-study
section: experience
parentEntryId: sample-role
date: 2025-06
title: Sample Automation
organization: Example Organisation
location: United Kingdom
retrievalPriority: high
---

# Sample Automation

## Overview

- The Owner built a [controlled workflow](https://example.test/workflow(v2)) and preserved
  this continuation inside the same logical bullet.

## Problem

- The process contained a repeatable control gap.

## Analysis

- Telemetry showed that a probable hardware issue remained unconfirmed.

## Results

- The controlled workflow reduced avoidable manual handling.

## Limitations

- The available evidence could not prove the hardware cause.

## Retrieval

### Retrieval Hints

- RETRIEVAL_ONLY_SENTINEL for automation and validation questions.

### Primary Tags

- case-study
- automation

### Secondary Tags

- validation
"""


def _resume_markdown() -> str:
    return """# Entries

## Sample Role

```yaml
id: sample-role
section: experience
startDate: 2025-01
endDate: 2025-12
title: Sample Role
```
"""
