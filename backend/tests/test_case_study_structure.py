from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASE_STUDIES_DIRECTORY = REPOSITORY_ROOT / "content" / "public" / "case-studies"
RESUME_PATH = REPOSITORY_ROOT / "content" / "public" / "resume.md"
TEMPLATE_PATH = CASE_STUDIES_DIRECTORY / "CASE_STUDY_TEMPLATE.md"

CASE_FILE_PATTERN = "*.case.md"
DOCUMENTATION_FILES = {"README.md", "CASE_STUDY_TEMPLATE.md"}

EXPECTED_CASE_IDS = {
    "case-corporate-borrower-credit-risk-process-analysis",
    "case-cross-border-skills-verification",
    "case-end-to-end-international-employment-service",
    "case-iot-buoy-fault-diagnosis",
    "case-kaizen-service-delivery-transformation",
    "case-payment-reconciliation-back-office",
    "case-pricing-data-erp-governance",
    "case-procurement-order-control",
    "case-recruitment-document-automation",
    "case-weee-reporting-automation",
}

REQUIRED_METADATA_FIELDS = {
    "schemaVersion",
    "id",
    "documentType",
    "section",
    "parentEntryId",
    "date",
    "title",
    "organization",
    "retrievalPriority",
}
OPTIONAL_METADATA_FIELDS = {"location"}
ALLOWED_METADATA_FIELDS = REQUIRED_METADATA_FIELDS | OPTIONAL_METADATA_FIELDS
REMOVED_METADATA_FIELDS = {
    "website",
    "visibility",
    "evidenceStatus",
    "sourceConfidence",
    "startDate",
    "endDate",
}

REQUIRED_LEVEL_TWO_SECTIONS = {
    "Overview",
    "Problem",
    "Analysis",
    "Results",
    "Retrieval",
}
REQUIRED_RETRIEVAL_SECTIONS = (
    "Retrieval Hints",
    "Primary Tags",
    "Secondary Tags",
)

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_PATTERN = re.compile(r"^(?P<year>\d{4})(?:-(?P<month>0[1-9]|1[0-2]))?$")
H1_PATTERN = re.compile(r"^# (.+)$", re.MULTILINE)
H2_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)
H3_PATTERN = re.compile(r"^### (.+)$", re.MULTILINE)
RESUME_ENTRY_METADATA_PATTERN = re.compile(
    r"^## .+?\n\n```yaml\n(?P<metadata>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)
MID_SENTENCE_OWNER_PATTERN = re.compile(
    r"\b(?:demonstrates|before) The Owner\b",
)
PLACEHOLDERS = (
    "Example Case Study",
    "case-example",
    "related-resume-entry-id",
    "distinctive-topic",
    "distinctive-technology",
    "supporting-skill",
    "<!-- no bullets -->",
)


def _case_files() -> tuple[Path, ...]:
    return tuple(sorted(CASE_STUDIES_DIRECTORY.rglob(CASE_FILE_PATTERN)))


CASE_FILES = _case_files()


def test_case_study_directory_contains_expected_case_files() -> None:
    assert CASE_STUDIES_DIRECTORY.is_dir(), (
        f"Case-study directory does not exist: {CASE_STUDIES_DIRECTORY}"
    )
    assert CASE_FILES, f"No {CASE_FILE_PATTERN} files found under {CASE_STUDIES_DIRECTORY}"

    actual_ids = {
        str(_parse_front_matter(path.read_text(encoding="utf-8"), path)[0].get("id", ""))
        for path in CASE_FILES
    }
    assert actual_ids == EXPECTED_CASE_IDS, (
        "Case-study collection differs from the expected public source set. "
        f"Missing: {sorted(EXPECTED_CASE_IDS - actual_ids)}; "
        f"unexpected: {sorted(actual_ids - EXPECTED_CASE_IDS)}"
    )


@pytest.mark.parametrize(
    "case_path",
    CASE_FILES,
    ids=lambda path: path.relative_to(CASE_STUDIES_DIRECTORY).as_posix(),
)
def test_each_case_study_matches_contract(case_path: Path) -> None:
    text = case_path.read_text(encoding="utf-8")
    metadata, body = _parse_front_matter(text, case_path)

    _validate_metadata(metadata, case_path)
    _validate_title(metadata, body, case_path)
    _validate_sections(body, case_path)
    _validate_retrieval(body, case_path)
    _validate_no_placeholders(text, case_path)
    _validate_owner_wording(text, case_path)


def test_case_study_ids_are_unique() -> None:
    paths_by_id: dict[str, Path] = {}
    duplicates: list[str] = []

    for case_path in CASE_FILES:
        metadata, _ = _parse_front_matter(
            case_path.read_text(encoding="utf-8"),
            case_path,
        )
        case_id = str(metadata.get("id", ""))
        if case_id in paths_by_id:
            duplicates.append(f"{case_id}: {paths_by_id[case_id]} and {case_path}")
        paths_by_id[case_id] = case_path

    assert not duplicates, f"Duplicate case-study ids found: {duplicates}"


def test_parent_entries_match_case_sections_and_dates() -> None:
    resume_entries = _resume_entries()
    missing_links: list[str] = []
    section_mismatches: list[str] = []
    date_mismatches: list[str] = []

    for case_path in CASE_FILES:
        metadata, _ = _parse_front_matter(
            case_path.read_text(encoding="utf-8"),
            case_path,
        )
        parent_id = str(metadata.get("parentEntryId", ""))
        parent = resume_entries.get(parent_id)
        if parent is None:
            missing_links.append(f"{case_path}: {parent_id}")
            continue

        if metadata.get("section") != parent.get("section"):
            section_mismatches.append(
                f"{case_path}: case={metadata.get('section')!r}, parent={parent.get('section')!r}"
            )

        date_error = _parent_date_error(metadata, parent)
        if date_error:
            date_mismatches.append(f"{case_path}: {date_error}")

    assert not missing_links, (
        f"Case studies reference parentEntryId values absent from resume.md: {missing_links}"
    )
    assert not section_mismatches, (
        f"Case-study sections must match their parent resume entries: {section_mismatches}"
    )
    assert not date_mismatches, (
        f"Case-study dates must remain within known parent entry periods: {date_mismatches}"
    )


def test_only_case_files_and_known_documentation_use_markdown_extension() -> None:
    unexpected_files = [
        path
        for path in CASE_STUDIES_DIRECTORY.rglob("*.md")
        if path.name not in DOCUMENTATION_FILES and not path.name.endswith(".case.md")
    ]

    assert not unexpected_files, (
        "Unexpected Markdown files in case-studies. Rename case sources to "
        f"*.case.md or classify them as documentation: {unexpected_files}"
    )


def test_case_study_template_reflects_current_schema() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    for field in REQUIRED_METADATA_FIELDS:
        assert re.search(rf"^{re.escape(field)}:", template, re.MULTILINE), (
            f"Case-study template is missing required metadata field: {field}"
        )
    for field in REMOVED_METADATA_FIELDS:
        assert not re.search(rf"^{re.escape(field)}:", template, re.MULTILINE), (
            f"Case-study template still contains removed metadata field: {field}"
        )
    assert "- case-study" in template, "Case-study template Primary Tags must include 'case-study'"


def _parse_front_matter(
    text: str,
    path: Path,
) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    assert normalized.startswith("---\n"), f"{path}: file must start with YAML front matter"

    parts = normalized.split("\n---\n", maxsplit=1)
    assert len(parts) == 2, f"{path}: YAML front matter must end with a closing --- line"

    raw_front_matter = parts[0][4:]
    body = parts[1].lstrip("\n")
    metadata = _safe_load_mapping(raw_front_matter, path)

    assert body.strip(), f"{path}: case-study body must not be empty"
    return metadata, body


def _safe_load_mapping(raw_yaml: str, path: Path) -> dict[str, Any]:
    try:
        metadata = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        pytest.fail(f"{path}: invalid YAML: {exc}")

    assert isinstance(metadata, dict), f"{path}: YAML metadata must be a mapping"
    return metadata


def _resume_entries() -> dict[str, dict[str, Any]]:
    assert RESUME_PATH.is_file(), f"Resume source does not exist: {RESUME_PATH}"
    resume_text = RESUME_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    entries: dict[str, dict[str, Any]] = {}

    for match in RESUME_ENTRY_METADATA_PATTERN.finditer(resume_text):
        metadata = _parse_resume_metadata(match.group("metadata"))
        entry_id = metadata.get("id")
        if entry_id:
            entries[entry_id] = metadata

    assert entries, f"No resume entry metadata found in {RESUME_PATH}"
    return entries


def _parse_resume_metadata(raw_metadata: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in raw_metadata.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip():
            metadata[key.strip()] = value.strip()
    return metadata


def _validate_metadata(metadata: dict[str, Any], path: Path) -> None:
    missing_fields = REQUIRED_METADATA_FIELDS - metadata.keys()
    unknown_fields = metadata.keys() - ALLOWED_METADATA_FIELDS

    assert not missing_fields, f"{path}: missing metadata fields: {sorted(missing_fields)}"
    assert not unknown_fields, f"{path}: unsupported metadata fields: {sorted(unknown_fields)}"

    assert metadata["schemaVersion"] == 1, f"{path}: schemaVersion must be 1"
    assert metadata["documentType"] == "case-study", f"{path}: documentType must be 'case-study'"
    assert metadata["section"] in {"experience", "education", "project"}, (
        f"{path}: unsupported section: {metadata['section']!r}"
    )
    assert metadata["retrievalPriority"] in {"low", "normal", "high"}, (
        f"{path}: unsupported retrievalPriority"
    )

    _assert_non_empty_string(metadata, "title", path)
    _assert_non_empty_string(metadata, "organization", path)
    _assert_slug(metadata, "id", path, required_prefix="case-")
    _assert_slug(metadata, "parentEntryId", path)
    _assert_date(metadata, "date", path)

    if metadata.get("location") is not None:
        _assert_non_empty_string(metadata, "location", path)


def _validate_title(
    metadata: dict[str, Any],
    body: str,
    path: Path,
) -> None:
    headings = H1_PATTERN.findall(body)

    assert len(headings) == 1, f"{path}: expected exactly one level-one heading"
    assert headings[0] == metadata["title"], (
        f"{path}: H1 title must match front-matter title exactly"
    )


def _validate_sections(body: str, path: Path) -> None:
    headings = H2_PATTERN.findall(body)

    assert headings, f"{path}: no level-two sections found"
    assert headings[0] == "Overview", f"{path}: first level-two section must be Overview"
    assert headings[-1] == "Retrieval", f"{path}: final level-two section must be Retrieval"
    assert len(headings) == len(set(headings)), f"{path}: duplicate level-two headings found"

    missing_sections = REQUIRED_LEVEL_TWO_SECTIONS - set(headings)
    assert not missing_sections, f"{path}: missing required sections: {sorted(missing_sections)}"

    for heading, content in _level_two_sections(body):
        assert content.strip(), f"{path}: section {heading!r} must not be empty"


def _validate_retrieval(body: str, path: Path) -> None:
    retrieval_text = _extract_h2(body, "Retrieval")
    headings = tuple(H3_PATTERN.findall(retrieval_text))

    assert headings == REQUIRED_RETRIEVAL_SECTIONS, (
        f"{path}: Retrieval must contain exactly these sections in order: "
        "Retrieval Hints, Primary Tags, Secondary Tags"
    )

    hints = _bullets(_extract_h3(retrieval_text, "Retrieval Hints"))
    primary_tags = _bullets(_extract_h3(retrieval_text, "Primary Tags"))
    secondary_tags = _bullets(_extract_h3(retrieval_text, "Secondary Tags"))

    assert hints, f"{path}: Retrieval Hints must contain at least one bullet"
    assert primary_tags, f"{path}: Primary Tags must contain at least one tag"
    assert "case-study" in primary_tags, f"{path}: Primary Tags must include 'case-study'"

    _assert_unique(primary_tags, path, "Primary Tags")
    _assert_unique(secondary_tags, path, "Secondary Tags")
    _assert_slug_list(primary_tags, path, "Primary Tags")
    _assert_slug_list(secondary_tags, path, "Secondary Tags")

    overlap = set(primary_tags) & set(secondary_tags)
    assert not overlap, f"{path}: tags must not appear in both groups: {sorted(overlap)}"


def _validate_no_placeholders(text: str, path: Path) -> None:
    placeholders = [value for value in PLACEHOLDERS if value in text]
    assert not placeholders, f"{path}: unresolved template placeholders: {placeholders}"


def _validate_owner_wording(text: str, path: Path) -> None:
    match = MID_SENTENCE_OWNER_PATTERN.search(text)
    assert match is None, f"{path}: use 'the Owner' inside a sentence; found {match.group(0)!r}"


def _parent_date_error(
    case_metadata: dict[str, Any],
    parent_metadata: dict[str, Any],
) -> str | None:
    parent_start = parent_metadata.get("startDate")
    parent_end = parent_metadata.get("endDate")
    case_date = case_metadata.get("date")

    if case_date is None:
        return None

    case_start = _date_sort_value(case_date, end=False)
    case_end = _date_sort_value(case_date, end=True)

    if parent_start is not None:
        parent_start_value = _date_sort_value(parent_start, end=False)
        if case_end < parent_start_value:
            return f"date {case_date!r} is earlier than parent startDate {parent_start!r}"

    if parent_end is not None:
        parent_end_value = _date_sort_value(parent_end, end=True)
        if case_start > parent_end_value:
            return f"date {case_date!r} is later than parent endDate {parent_end!r}"

    return None


def _assert_non_empty_string(
    metadata: dict[str, Any],
    field: str,
    path: Path,
) -> None:
    value = metadata[field]
    assert isinstance(value, str) and value.strip(), f"{path}: {field} must be a non-empty string"


def _assert_slug(
    metadata: dict[str, Any],
    field: str,
    path: Path,
    *,
    required_prefix: str | None = None,
) -> None:
    _assert_non_empty_string(metadata, field, path)
    value = metadata[field]

    assert SLUG_PATTERN.fullmatch(value), f"{path}: {field} must be lowercase kebab-case"
    if required_prefix is not None:
        assert value.startswith(required_prefix), (
            f"{path}: {field} must start with {required_prefix!r}"
        )


def _assert_date(
    metadata: dict[str, Any],
    field: str,
    path: Path,
) -> None:
    value = metadata[field]

    assert isinstance(value, (str, int)), f"{path}: {field} must be YYYY or YYYY-MM"
    assert DATE_PATTERN.fullmatch(str(value)), f"{path}: {field} must be YYYY or YYYY-MM"


def _date_sort_value(value: str | int, *, end: bool) -> date:
    match = DATE_PATTERN.fullmatch(str(value))
    assert match is not None

    year = int(match.group("year"))
    month_text = match.group("month")
    month = int(month_text) if month_text else (12 if end else 1)
    return date(year, month, 1)


def _level_two_sections(body: str) -> tuple[tuple[str, str], ...]:
    matches = list(H2_PATTERN.finditer(body))
    sections: list[tuple[str, str]] = []

    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections.append((match.group(1), body[start:end].strip()))

    return tuple(sections)


def _extract_h2(body: str, heading: str) -> str:
    for current_heading, content in _level_two_sections(body):
        if current_heading == heading:
            return content
    raise AssertionError(f"Missing level-two section: {heading}")


def _extract_h3(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^### {re.escape(heading)}\s*$\n(?P<content>.*?)(?=^### |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)

    assert match is not None, f"Missing level-three section: {heading}"
    return match.group("content").strip()


def _bullets(text: str) -> tuple[str, ...]:
    return tuple(
        line[2:].strip() for line in text.splitlines() if line.startswith("- ") and line[2:].strip()
    )


def _assert_unique(
    values: tuple[str, ...],
    path: Path,
    label: str,
) -> None:
    assert len(values) == len(set(values)), f"{path}: duplicate values in {label}"


def _assert_slug_list(
    values: tuple[str, ...],
    path: Path,
    label: str,
) -> None:
    invalid = [value for value in values if not SLUG_PATTERN.fullmatch(value)]
    assert not invalid, f"{path}: {label} must use lowercase kebab-case values: {invalid}"
