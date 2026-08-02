from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.rag.case_study_contract import (
    CaseStudyContractError,
    ResumeEntry,
    discover_case_study_files,
    parse_case_study_markdown,
    parse_resume_entries,
    validate_case_study_collection,
)


def _valid_markdown(*, case_id: str = "case-contract-example") -> str:
    return f"""---
schemaVersion: 1
id: {case_id}
documentType: case-study
section: experience
parentEntryId: resume-example
date: 2025-06
title: Example Case
organization: Example Organisation
retrievalPriority: normal
---

# Example Case

## Overview

- Overview content.

## Problem

- Problem content.

## Analysis

- Analysis content.

## Implementation

- Implementation content.

## Results

- Results content.

## Limitations

- Limitations content.

## Retrieval

### Retrieval Hints

- Useful for questions about the example.

### Primary Tags

- case-study
- automation

### Secondary Tags

- python
"""


def _parse(markdown: str):
    return parse_case_study_markdown(markdown, source_path=Path("example.case.md"))


@pytest.mark.parametrize(
    ("markdown", "message"),
    [
        (_valid_markdown().removeprefix("---\n"), "must start with YAML front matter"),
        (_valid_markdown().replace("\n---\n\n#", "\n\n#", 1), "must end with a closing"),
        (_valid_markdown().replace("title: Example Case", "title: ["), "invalid YAML"),
    ],
)
def test_rejects_invalid_front_matter(markdown: str, message: str) -> None:
    with pytest.raises(CaseStudyContractError, match=message):
        _parse(markdown)


def test_rejects_non_mapping_front_matter() -> None:
    markdown = _valid_markdown()
    closing = markdown.index("\n---\n", 4)
    markdown = "---\n- item" + markdown[closing:]

    with pytest.raises(CaseStudyContractError, match="must be a mapping"):
        _parse(markdown)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            "retrievalPriority: normal",
            "retrievalPriority: normal\nunknownField: value",
            "Extra inputs are not permitted",
        ),
        ("id: case-contract-example", "id: Example_Case", "lowercase kebab-case"),
        ("id: case-contract-example", "id: example", "must start with 'case-'"),
        ("date: 2025-06", "date: 2025-13", "must use YYYY or YYYY-MM"),
        ("organization: Example Organisation", "organization: ''", "non-empty string"),
    ],
)
def test_rejects_invalid_metadata(old: str, new: str, message: str) -> None:
    with pytest.raises(CaseStudyContractError, match=message):
        _parse(_valid_markdown().replace(old, new))


def test_accepts_year_as_yaml_integer_and_normalizes_it() -> None:
    document = _parse(_valid_markdown().replace("date: 2025-06", "date: 2025"))

    assert document.metadata.date == "2025"


@pytest.mark.parametrize(
    ("markdown", "message"),
    [
        (_valid_markdown().replace("# Example Case\n", ""), "exactly one level-one"),
        (
            _valid_markdown().replace("# Example Case", "# Different Case"),
            "must match front-matter title",
        ),
        (
            _valid_markdown().replace("## Results\n\n- Results content.\n\n", ""),
            "missing required level-two sections",
        ),
        (
            _valid_markdown().replace(
                "## Limitations\n\n- Limitations content.\n\n## Retrieval",
                "## Retrieval",
            )
            + "\n## Limitations\n\n- Limitations content.\n",
            "final level-two section must be Retrieval",
        ),
        (
            _valid_markdown().replace(
                "## Results\n\n- Results content.",
                "## Results\n\n- Results content.\n\n## Results!\n\n- Duplicate.",
            ),
            "duplicate normalized level-two section slug",
        ),
        (
            _valid_markdown().replace("- Results content.", ""),
            "section 'Results' must not be empty",
        ),
    ],
)
def test_rejects_invalid_document_structure(markdown: str, message: str) -> None:
    with pytest.raises(CaseStudyContractError, match=message):
        _parse(markdown)


@pytest.mark.parametrize(
    ("markdown", "message"),
    [
        (
            _valid_markdown().replace("### Retrieval Hints", "### Search Hints"),
            "Retrieval must contain exactly",
        ),
        (
            _valid_markdown().replace("- case-study\n", ""),
            "Primary Tags must include 'case-study'",
        ),
        (
            _valid_markdown().replace("- automation\n", "- automation\n- automation\n"),
            "duplicate values in Primary Tags",
        ),
        (
            _valid_markdown().replace("- python\n", "- automation\n"),
            "tags must not appear in both groups",
        ),
        (
            _valid_markdown().replace("- python\n", "- Python API\n"),
            "lowercase kebab-case",
        ),
        (
            _valid_markdown().replace(
                "## Analysis\n\n- Analysis content.",
                "## Analysis\n\n### Unsupported\n\n- Analysis content.",
            ),
            "level-three headings are only allowed in Retrieval",
        ),
    ],
)
def test_rejects_invalid_retrieval_metadata(markdown: str, message: str) -> None:
    with pytest.raises(CaseStudyContractError, match=message):
        _parse(markdown)


def test_allows_an_empty_secondary_tag_group() -> None:
    document = _parse(_valid_markdown().replace("- python\n", ""))

    assert document.retrieval.secondary_tags == ()


def test_preserves_multiline_retrieval_bullets() -> None:
    document = _parse(
        _valid_markdown().replace(
            "- Useful for questions about the example.",
            "- Useful for questions about the example,\n  including multiline details.",
        )
    )

    assert document.retrieval.hints == (
        "Useful for questions about the example,\nincluding multiline details.",
    )


def test_ignores_headings_inside_fenced_code() -> None:
    markdown = _valid_markdown().replace(
        "- Analysis content.",
        "```text\n## Not A Section\n### Not Retrieval Metadata\n```\n\n- Analysis content.",
    )

    document = _parse(markdown)

    assert "not-a-section" not in {section.slug for section in document.sections}


@pytest.mark.parametrize(
    "placeholder",
    ["<case-slug>", "Example Case Study", "<!-- no bullets -->"],
)
def test_rejects_unresolved_template_placeholders(placeholder: str) -> None:
    with pytest.raises(CaseStudyContractError, match="unresolved template placeholders"):
        _parse(_valid_markdown().replace("Overview content.", placeholder))


def test_discovers_only_case_study_sources(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "README.md").write_text("docs", encoding="utf-8")
    (tmp_path / "CASE_STUDY_TEMPLATE.md").write_text("template", encoding="utf-8")
    first = tmp_path / "one.case.md"
    second = nested / "two.case.md"
    first.write_text(_valid_markdown(), encoding="utf-8")
    second.write_text(_valid_markdown(case_id="case-second"), encoding="utf-8")

    assert discover_case_study_files(tmp_path) == (second, first)


def test_parses_resume_entry_metadata_without_treating_markdown_links_as_yaml() -> None:
    resume = """# Entries

## Example

```yaml
id: resume-example
section: experience
startDate: 2024-01
endDate: present
title: Example
organization: [Example](https://example.test)
```
"""

    entries = parse_resume_entries(resume)

    assert entries["resume-example"] == ResumeEntry(
        id="resume-example",
        section="experience",
        start_date="2024-01",
        end_date="present",
    )


def test_rejects_duplicate_resume_entry_ids() -> None:
    block = """## Example

```yaml
id: resume-example
section: experience
```
"""

    with pytest.raises(CaseStudyContractError, match="duplicate resume entry id"):
        parse_resume_entries(f"# Entries\n\n{block}\n{block}")


def _document(*, case_id: str = "case-contract-example"):
    return _parse(_valid_markdown(case_id=case_id))


def _resume_entry(**changes: str | None) -> ResumeEntry:
    values: dict[str, str | None] = {
        "id": "resume-example",
        "section": "experience",
        "start_date": "2024-01",
        "end_date": "2026-12",
    }
    values.update(changes)
    return ResumeEntry(**values)  # type: ignore[arg-type]


def test_rejects_duplicate_case_ids() -> None:
    document = _document()

    with pytest.raises(CaseStudyContractError, match="duplicate case-study id"):
        validate_case_study_collection(
            [document, replace(document, source_path=Path("duplicate.case.md"))],
            {"resume-example": _resume_entry()},
        )


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ({}, "is absent from resume"),
        (
            {"resume-example": _resume_entry(section="education")},
            "does not match parent section",
        ),
        (
            {"resume-example": _resume_entry(start_date="2026-01")},
            "earlier than parent startDate",
        ),
        (
            {"resume-example": _resume_entry(end_date="2024-12")},
            "later than parent endDate",
        ),
    ],
)
def test_rejects_invalid_parent_relationships(
    entries: dict[str, ResumeEntry],
    message: str,
) -> None:
    with pytest.raises(CaseStudyContractError, match=message):
        validate_case_study_collection([_document()], entries)


def test_rejects_unexpected_collection_ids() -> None:
    with pytest.raises(CaseStudyContractError, match="differs from the expected source set"):
        validate_case_study_collection(
            [_document()],
            {"resume-example": _resume_entry()},
            expected_case_ids={"case-required"},
        )
