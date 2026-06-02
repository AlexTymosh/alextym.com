import json
from pathlib import Path

import pytest

from app.rag.resume_rag_source import (
    build_resume_rag_document,
    render_resume_rag_json,
    main,
    render_resume_rag_preview,
    write_resume_rag_outputs,
)

CONCISE_SENTINEL = "CONCISE_ONLY_SENTINEL"
DETAILED_SENTINEL = "DETAILED_ONLY_SENTINEL"
FACT_SENTINEL = "ANSWER_FACT_SENTINEL"
HINT_SENTINEL = "RETRIEVAL_HINT_SENTINEL"


def test_extracts_only_answer_facts_as_content() -> None:
    document = build_resume_rag_document(_fixture_markdown())
    chunk = _get_chunk(document, "sample-entry")

    assert FACT_SENTINEL in chunk.content
    assert HINT_SENTINEL not in chunk.content
    assert CONCISE_SENTINEL not in chunk.content
    assert DETAILED_SENTINEL not in chunk.content


def test_retrieval_hints_are_stored_separately() -> None:
    document = build_resume_rag_document(_fixture_markdown())
    chunk = _get_chunk(document, "sample-entry")

    assert any(HINT_SENTINEL in hint for hint in chunk.retrieval_hints)
    assert all(HINT_SENTINEL not in fact for fact in chunk.answer_facts)


def test_primary_and_secondary_tags_are_explicit() -> None:
    document = build_resume_rag_document(_fixture_markdown())
    chunk = _get_chunk(document, "sample-entry")

    assert chunk.payload.primary_tags == ("api", "automation", "odoo")
    assert chunk.payload.secondary_tags == ("dashboards", "reporting")
    assert "python" not in chunk.payload.tags
    assert "fastapi" not in chunk.payload.tags


def test_markdown_links_are_split_from_source_fields() -> None:
    document = build_resume_rag_document(_fixture_markdown())
    chunk = _get_chunk(document, "sample-entry")

    assert chunk.source.title == "Sample Entry"
    assert chunk.source.title_url == "/evidence/sample-entry"
    assert chunk.source.organization == "Example Ltd"
    assert chunk.source.organization_url == "https://example.org"


def test_vector_inputs_do_not_contain_markdown_links_or_urls() -> None:
    document = build_resume_rag_document(_fixture_markdown())
    serialized_inputs = json.dumps(
        [chunk.vector_inputs for chunk in document.chunks],
        ensure_ascii=False,
    )

    assert "](http" not in serialized_inputs
    assert "https://" not in serialized_inputs
    assert "/evidence/" not in serialized_inputs


def test_structured_output_supports_future_retrieval_modes() -> None:
    document = build_resume_rag_document(_fixture_markdown())
    payload = json.loads(render_resume_rag_json(document))
    chunk = payload["chunks"][0]

    assert payload["schema_version"] == 2
    assert chunk["payload"]["visibility"] == "public"
    assert chunk["payload"]["topic"]
    assert chunk["payload"]["primary_tags"]
    assert "body_dense" in chunk["vector_inputs"]
    assert "title_dense" in chunk["vector_inputs"]
    assert "keywords_sparse" in chunk["vector_inputs"]
    assert "rerank_text" in chunk["vector_inputs"]
    assert "compression_text" in chunk["vector_inputs"]
    assert "hybrid" in chunk["retrieval"]["modes"]
    assert "parent_child" in chunk["retrieval"]["modes"]
    assert "context_compression" in chunk["retrieval"]["modes"]


def test_preview_output_is_not_the_embedding_source() -> None:
    document = build_resume_rag_document(_fixture_markdown())
    preview = render_resume_rag_preview(document)

    assert FACT_SENTINEL in preview
    assert CONCISE_SENTINEL not in preview
    assert DETAILED_SENTINEL not in preview
    assert "human-readable preview" in preview
    assert "### RAG" not in preview


def test_write_resume_rag_outputs_json_and_tmp_preview(tmp_path: Path) -> None:
    source_path = tmp_path / "resume.md"
    json_output = tmp_path / "backend" / "knowledge" / "resume.chunks.json"
    preview_output = tmp_path / ".tmp" / "preview" / "resume-rag-preview.md"
    source_path.write_text(_fixture_markdown(), encoding="utf-8")

    document = write_resume_rag_outputs(
        source_path=source_path,
        json_output_path=json_output,
        preview_output_path=preview_output,
    )

    assert len(document.chunks) == 2
    assert json_output.exists()
    assert preview_output.exists()
    assert not (tmp_path / "backend" / "knowledge" / "resume.generated.md").exists()
    assert FACT_SENTINEL in json_output.read_text(encoding="utf-8")
    assert FACT_SENTINEL in preview_output.read_text(encoding="utf-8")


def test_main_prints_readable_no_colour_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = tmp_path / "resume.md"
    json_output = tmp_path / "backend" / "knowledge" / "resume.chunks.json"
    preview_output = tmp_path / ".tmp" / "preview" / "resume-rag-preview.md"
    source_path.write_text(_fixture_markdown(), encoding="utf-8")
    monkeypatch.setenv("NO_COLOR", "1")

    main(
        [
            "--source",
            str(source_path),
            "--json-output",
            str(json_output),
            "--preview-output",
            str(preview_output),
        ]
    )

    output = capsys.readouterr().out

    assert "\x1b[" not in output
    assert "[OK] Extracted 2 RAG chunk(s)." in output
    assert "[JSON]" in output
    assert "[PREVIEW]" in output
    assert "[NEXT] Review the generated JSON" in output


def test_main_prints_colour_labels(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = tmp_path / "resume.md"
    json_output = tmp_path / "backend" / "knowledge" / "resume.chunks.json"
    preview_output = tmp_path / ".tmp" / "preview" / "resume-rag-preview.md"
    source_path.write_text(_fixture_markdown(), encoding="utf-8")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("TERM", raising=False)

    main(
        [
            "--source",
            str(source_path),
            "--json-output",
            str(json_output),
            "--preview-output",
            str(preview_output),
        ]
    )

    output = capsys.readouterr().out

    assert "\x1b[32m[OK]\x1b[0m" in output
    assert "\x1b[36m[JSON]\x1b[0m" in output
    assert "\x1b[36m[PREVIEW]\x1b[0m" in output
    assert "\x1b[33m[NEXT]\x1b[0m" in output


def test_legacy_flat_rag_section_still_supported() -> None:
    document = build_resume_rag_document(_legacy_fixture_markdown())
    chunk = _get_chunk(document, "legacy-entry")

    assert chunk.answer_facts == ("Alex legacy fact.",)
    assert chunk.payload.primary_tags == ("resume",)


def test_structured_rag_requires_answer_facts() -> None:
    with pytest.raises(ValueError, match="Answer Facts"):
        build_resume_rag_document(_fixture_without_answer_facts())


def test_structured_rag_requires_primary_tags() -> None:
    with pytest.raises(ValueError, match="Primary Tags"):
        build_resume_rag_document(_fixture_without_primary_tags())


def test_answer_facts_must_not_contain_retrieval_hints() -> None:
    with pytest.raises(ValueError, match="retrieval hints"):
        build_resume_rag_document(_fixture_with_meta_answer_fact())


def _get_chunk(document: object, source_id: str) -> object:
    return next(chunk for chunk in document.chunks if chunk.source.id == source_id)


def _fixture_markdown() -> str:
    return f"""
---
version: 1
owner: Alex Tymoshenko
scope: public website resume source with RAG-only sections
rag_indexing: true
---

# Summary

## Concise

{CONCISE_SENTINEL} summary.

## Detailed

{DETAILED_SENTINEL} summary.

## RAG

#### Answer Facts

- Alex summary {FACT_SENTINEL}.

#### Retrieval Hints

- Summary retrieval {HINT_SENTINEL}.

#### Primary Tags

- automation
- API

#### Secondary Tags

- reporting

# Entries

## Sample Entry

```yaml
id: sample-entry
section: experience
startDate: 2024-01
endDate: 2024-02
title: [Sample Entry](/evidence/sample-entry)
organization: [Example Ltd](https://example.org)
location: United Kingdom
```

### Concise

- {CONCISE_SENTINEL} entry.

### Detailed

- {DETAILED_SENTINEL} entry.

### RAG

#### Answer Facts

- Alex entry {FACT_SENTINEL} with Odoo, APIs and automation.

#### Retrieval Hints

- {HINT_SENTINEL} for reporting dashboards and ERP integration.
- Mentions later Python/FastAPI transition only as context.

#### Primary Tags

- Odoo
- API
- automation

#### Secondary Tags

- reporting
- dashboards

## Entry Without RAG

```yaml
id: no-rag-entry
section: experience
startDate: 2023-01
endDate: 2023-02
title: Entry Without RAG
```

### Concise

- {CONCISE_SENTINEL} no rag.

### Detailed

- {DETAILED_SENTINEL} no rag.

# Additional Sections

## Languages

- English: B1/B2
"""


def _legacy_fixture_markdown() -> str:
    return """
# Summary

## Concise

Visible.

## Detailed

Visible.

# Entries

## Legacy Entry

```yaml
id: legacy-entry
section: experience
startDate: 2024-01
endDate: 2024-02
title: Legacy Entry
```

### Concise

- Visible.

### Detailed

- Visible.

### RAG

- Alex legacy fact.

# Additional Sections

## Languages

- English: B1/B2
"""


def _fixture_without_answer_facts() -> str:
    return _fixture_markdown().replace(
        f"#### Answer Facts\n\n- Alex entry {FACT_SENTINEL} with Odoo, APIs and automation.",
        "#### Answer Facts\n\n<!-- no bullets -->",
    )


def _fixture_without_primary_tags() -> str:
    return _fixture_markdown().replace(
        "#### Primary Tags\n\n- Odoo\n- API\n- automation",
        "#### Primary Tags\n\n<!-- no bullets -->",
    )


def _fixture_with_meta_answer_fact() -> str:
    return _fixture_markdown().replace(
        f"Alex entry {FACT_SENTINEL} with Odoo, APIs and automation.",
        "This experience is relevant to questions about Odoo.",
    )
