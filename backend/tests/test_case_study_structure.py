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

CASE_FILE_PATTERN = "*.case.md"
DOCUMENTATION_FILES = {"README.md", "CASE_STUDY_TEMPLATE.md"}

REQUIRED_METADATA_FIELDS = {
    "schemaVersion",
    "id",
    "documentType",
    "section",
    "website",
    "parentExperienceId",
    "startDate",
    "title",
    "organization",
    "visibility",
    "sourceConfidence",
    "retrievalPriority",
}
OPTIONAL_METADATA_FIELDS = {"endDate", "location"}
ALLOWED_METADATA_FIELDS = REQUIRED_METADATA_FIELDS | OPTIONAL_METADATA_FIELDS

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
RESUME_ID_PATTERN = re.compile(
    r"^id:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$",
    re.MULTILINE,
)
PLACEHOLDERS = (
    "Example Case Study",
    "case-example",
    "related-resume-entry-id",
    "distinctive-topic",
    "distinctive-technology",
    "<!-- no bullets -->",
)


def _case_files() -> tuple[Path, ...]:
    return tuple(sorted(CASE_STUDIES_DIRECTORY.rglob(CASE_FILE_PATTERN)))


CASE_FILES = _case_files()


def test_case_study_directory_contains_case_files() -> None:
    assert CASE_STUDIES_DIRECTORY.is_dir(), (
        f"Case-study directory does not exist: {CASE_STUDIES_DIRECTORY}"
    )
    assert CASE_FILES, (
        f"No {CASE_FILE_PATTERN} files found under {CASE_STUDIES_DIRECTORY}"
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
            duplicates.append(
                f"{case_id}: {paths_by_id[case_id]} and {case_path}"
            )
        paths_by_id[case_id] = case_path

    assert not duplicates, f"Duplicate case-study ids found: {duplicates}"


def test_parent_experience_ids_exist_in_resume() -> None:
    assert RESUME_PATH.is_file(), f"Resume source does not exist: {RESUME_PATH}"
    resume_ids = set(
        RESUME_ID_PATTERN.findall(RESUME_PATH.read_text(encoding="utf-8"))
    )
    missing_links: list[str] = []

    for case_path in CASE_FILES:
        metadata, _ = _parse_front_matter(
            case_path.read_text(encoding="utf-8"),
            case_path,
        )
        parent_id = str(metadata.get("parentExperienceId", ""))
        if parent_id not in resume_ids:
            missing_links.append(f"{case_path}: {parent_id}")

    assert not missing_links, (
        "Case studies reference parentExperienceId values absent from resume.md: "
        f"{missing_links}"
    )


def test_only_case_files_and_known_documentation_use_markdown_extension() -> None:
    unexpected_files = [
        path
        for path in CASE_STUDIES_DIRECTORY.rglob("*.md")
        if path.name not in DOCUMENTATION_FILES
        and not path.name.endswith(".case.md")
    ]

    assert not unexpected_files, (
        "Unexpected Markdown files in case-studies. Rename case sources to "
        f"*.case.md or classify them as documentation: {unexpected_files}"
    )


def _parse_front_matter(
    text: str,
    path: Path,
) -> tuple[dict[str, Any], str]:
    normalized = text.replace("\r\n", "\n")
    assert normalized.startswith("---\n"), (
        f"{path}: file must start with YAML front matter"
    )

    parts = normalized.split("\n---\n", maxsplit=1)
    assert len(parts) == 2, (
        f"{path}: YAML front matter must end with a closing --- line"
    )

    raw_front_matter = parts[0][4:]
    body = parts[1].lstrip("\n")

    try:
        metadata = yaml.safe_load(raw_front_matter)
    except yaml.YAMLError as exc:
        pytest.fail(f"{path}: invalid YAML front matter: {exc}")

    assert isinstance(metadata, dict), (
        f"{path}: YAML front matter must be a mapping"
    )
    assert body.strip(), f"{path}: case-study body must not be empty"
    return metadata, body


def _validate_metadata(metadata: dict[str, Any], path: Path) -> None:
    missing_fields = REQUIRED_METADATA_FIELDS - metadata.keys()
    unknown_fields = metadata.keys() - ALLOWED_METADATA_FIELDS

    assert not missing_fields, (
        f"{path}: missing metadata fields: {sorted(missing_fields)}"
    )
    assert not unknown_fields, (
        f"{path}: unsupported metadata fields: {sorted(unknown_fields)}"
    )

    assert metadata["schemaVersion"] == 1, (
        f"{path}: schemaVersion must be 1"
    )
    assert metadata["documentType"] == "case-study", (
        f"{path}: documentType must be 'case-study'"
    )
    assert metadata["section"] in {"experience", "education", "project"}, (
        f"{path}: unsupported section: {metadata['section']!r}"
    )
    assert isinstance(metadata["website"], bool), (
        f"{path}: website must be a boolean"
    )
    assert metadata["visibility"] == "public", (
        f"{path}: visibility must be 'public'"
    )
    assert metadata["sourceConfidence"] in {
        "self-reported",
        "documented",
        "verified",
    }, f"{path}: unsupported sourceConfidence"
    assert metadata["retrievalPriority"] in {"low", "normal", "high"}, (
        f"{path}: unsupported retrievalPriority"
    )

    _assert_non_empty_string(metadata, "title", path)
    _assert_non_empty_string(metadata, "organization", path)
    _assert_slug(metadata, "id", path, required_prefix="case-")
    _assert_slug(metadata, "parentExperienceId", path)
    _assert_date(metadata, "startDate", path)

    if metadata.get("endDate") is not None:
        _assert_date(metadata, "endDate", path)
        assert _date_sort_value(
            metadata["endDate"],
            end=True,
        ) >= _date_sort_value(
            metadata["startDate"],
            end=False,
        ), f"{path}: endDate must not be earlier than startDate"

    if metadata.get("location") is not None:
        _assert_non_empty_string(metadata, "location", path)


def _validate_title(
    metadata: dict[str, Any],
    body: str,
    path: Path,
) -> None:
    headings = H1_PATTERN.findall(body)

    assert len(headings) == 1, (
        f"{path}: expected exactly one level-one heading"
    )
    assert headings[0] == metadata["title"], (
        f"{path}: H1 title must match front-matter title exactly"
    )


def _validate_sections(body: str, path: Path) -> None:
    headings = H2_PATTERN.findall(body)

    assert headings, f"{path}: no level-two sections found"
    assert headings[0] == "Overview", (
        f"{path}: first level-two section must be Overview"
    )
    assert headings[-1] == "Retrieval", (
        f"{path}: final level-two section must be Retrieval"
    )
    assert len(headings) == len(set(headings)), (
        f"{path}: duplicate level-two headings found"
    )

    missing_sections = REQUIRED_LEVEL_TWO_SECTIONS - set(headings)
    assert not missing_sections, (
        f"{path}: missing required sections: {sorted(missing_sections)}"
    )

    for heading, content in _level_two_sections(body):
        assert content.strip(), (
            f"{path}: section {heading!r} must not be empty"
        )


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

    assert hints, (
        f"{path}: Retrieval Hints must contain at least one bullet"
    )
    assert primary_tags, (
        f"{path}: Primary Tags must contain at least one tag"
    )
    assert "case-study" in primary_tags, (
        f"{path}: Primary Tags must include 'case-study'"
    )

    _assert_unique(primary_tags, path, "Primary Tags")
    _assert_unique(secondary_tags, path, "Secondary Tags")
    _assert_slug_list(primary_tags, path, "Primary Tags")
    _assert_slug_list(secondary_tags, path, "Secondary Tags")

    overlap = set(primary_tags) & set(secondary_tags)
    assert not overlap, (
        f"{path}: tags must not appear in both groups: {sorted(overlap)}"
    )


def _validate_no_placeholders(text: str, path: Path) -> None:
    placeholders = [value for value in PLACEHOLDERS if value in text]
    assert not placeholders, (
        f"{path}: unresolved template placeholders: {placeholders}"
    )


def _assert_non_empty_string(
    metadata: dict[str, Any],
    field: str,
    path: Path,
) -> None:
    value = metadata[field]
    assert isinstance(value, str) and value.strip(), (
        f"{path}: {field} must be a non-empty string"
    )


def _assert_slug(
    metadata: dict[str, Any],
    field: str,
    path: Path,
    *,
    required_prefix: str | None = None,
) -> None:
    _assert_non_empty_string(metadata, field, path)
    value = metadata[field]

    assert SLUG_PATTERN.fullmatch(value), (
        f"{path}: {field} must be lowercase kebab-case"
    )
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

    assert isinstance(value, (str, int)), (
        f"{path}: {field} must be YYYY or YYYY-MM"
    )
    assert DATE_PATTERN.fullmatch(str(value)), (
        f"{path}: {field} must be YYYY or YYYY-MM"
    )


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
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(body)
        )
        sections.append((match.group(1), body[start:end].strip()))

    return tuple(sections)


def _extract_h2(body: str, heading: str) -> str:
    for current_heading, content in _level_two_sections(body):
        if current_heading == heading:
            return content
    raise AssertionError(f"Missing level-two section: {heading}")


def _extract_h3(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^### {re.escape(heading)}\s*$\n"
        rf"(?P<content>.*?)(?=^### |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)

    assert match is not None, (
        f"Missing level-three section: {heading}"
    )
    return match.group("content").strip()


def _bullets(text: str) -> tuple[str, ...]:
    return tuple(
        line[2:].strip()
        for line in text.splitlines()
        if line.startswith("- ") and line[2:].strip()
    )


def _assert_unique(
    values: tuple[str, ...],
    path: Path,
    label: str,
) -> None:
    assert len(values) == len(set(values)), (
        f"{path}: duplicate values in {label}"
    )


def _assert_slug_list(
    values: tuple[str, ...],
    path: Path,
    label: str,
) -> None:
    invalid = [
        value
        for value in values
        if not SLUG_PATTERN.fullmatch(value)
    ]
    assert not invalid, (
        f"{path}: {label} must use lowercase kebab-case values: {invalid}"
    )
