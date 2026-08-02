from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Mapping, Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

CASE_STUDY_FILE_PATTERN = "*.case.md"
DOCUMENTATION_FILE_NAMES = frozenset({"README.md", "CASE_STUDY_TEMPLATE.md"})
REQUIRED_LEVEL_TWO_SECTIONS = frozenset({"Overview", "Problem", "Analysis", "Results", "Retrieval"})
RETRIEVAL_LEVEL_THREE_SECTIONS = (
    "Retrieval Hints",
    "Primary Tags",
    "Secondary Tags",
)

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE_PATTERN = re.compile(r"^(?P<year>\d{4})(?:-(?P<month>0[1-9]|1[0-2]))?$")
_HEADING_PATTERN = re.compile(r"^(?P<marks>#{1,3})[ \t]+(?P<title>.+?)[ \t]*$")
_FENCE_PATTERN = re.compile(r"^[ \t]{0,3}(?P<marker>`{3,}|~{3,})")
_RESUME_ENTRY_PATTERN = re.compile(
    r"^## .+?\n\n```yaml\n(?P<metadata>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)
_ANGLE_PLACEHOLDER_PATTERN = re.compile(r"<[^>\n]+>")
_KNOWN_PLACEHOLDERS = (
    "Example Case Study",
    "case-example",
    "related-resume-entry-id",
    "distinctive-topic",
    "distinctive-technology",
    "supporting-skill",
    "<!-- no bullets -->",
)


class CaseStudyContractError(ValueError):
    """Raised when a case-study source violates the canonical source contract."""


class CaseStudyMetadata(BaseModel):
    """Strict front-matter schema for a public case-study source."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        strict=True,
        str_strip_whitespace=True,
    )

    schema_version: Literal[1] = Field(alias="schemaVersion")
    id: str
    document_type: Literal["case-study"] = Field(alias="documentType")
    section: Literal["experience", "education", "project"]
    parent_entry_id: str = Field(alias="parentEntryId")
    date: str
    title: str
    organization: str
    retrieval_priority: Literal["low", "normal", "high"] = Field(alias="retrievalPriority")
    location: str | None = None

    @field_validator("date", mode="before")
    @classmethod
    def normalize_date(cls, value: object) -> object:
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return value

    @field_validator("id")
    @classmethod
    def validate_case_id(cls, value: str) -> str:
        _validate_slug(value, field_name="id")
        if not value.startswith("case-"):
            raise ValueError("must start with 'case-'")
        return value

    @field_validator("parent_entry_id")
    @classmethod
    def validate_parent_entry_id(cls, value: str) -> str:
        _validate_slug(value, field_name="parentEntryId")
        return value

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        if not _DATE_PATTERN.fullmatch(value):
            raise ValueError("must use YYYY or YYYY-MM")
        return value

    @field_validator("title", "organization", "location")
    @classmethod
    def validate_non_empty_text(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("must be a non-empty string")
        return value


@dataclass(frozen=True)
class CaseStudySection:
    title: str
    slug: str
    content: str


@dataclass(frozen=True)
class CaseStudyRetrieval:
    hints: tuple[str, ...]
    primary_tags: tuple[str, ...]
    secondary_tags: tuple[str, ...]


@dataclass(frozen=True)
class CaseStudyDocument:
    source_path: Path
    metadata: CaseStudyMetadata
    title: str
    sections: tuple[CaseStudySection, ...]
    retrieval: CaseStudyRetrieval

    @property
    def answer_sections(self) -> tuple[CaseStudySection, ...]:
        return tuple(section for section in self.sections if section.slug != "retrieval")


@dataclass(frozen=True)
class ResumeEntry:
    id: str
    section: str
    start_date: str | None
    end_date: str | None


@dataclass(frozen=True)
class CaseStudyCollection:
    documents: tuple[CaseStudyDocument, ...]
    resume_entries: Mapping[str, ResumeEntry]


@dataclass(frozen=True)
class _Heading:
    level: int
    title: str
    line_index: int


def discover_case_study_files(directory: Path) -> tuple[Path, ...]:
    """Return only canonical ``*.case.md`` files in deterministic path order."""

    if not directory.is_dir():
        raise CaseStudyContractError(f"Case-study directory does not exist: {directory}")

    files = tuple(sorted(directory.rglob(CASE_STUDY_FILE_PATTERN)))
    if not files:
        raise CaseStudyContractError(f"No {CASE_STUDY_FILE_PATTERN} files found under {directory}")
    return files


def load_case_study(path: Path) -> CaseStudyDocument:
    try:
        markdown = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CaseStudyContractError(f"Unable to read case-study source {path}: {exc}") from exc
    return parse_case_study_markdown(markdown, source_path=path)


def parse_case_study_markdown(
    markdown: str,
    *,
    source_path: Path | str = Path("<memory>"),
) -> CaseStudyDocument:
    """Parse and validate one canonical case-study Markdown document.

    The source format intentionally supports a narrow Markdown contract: YAML front
    matter, one H1, semantic H2 sections, and the three required H3 sections inside
    ``Retrieval``. Fenced-code contents are ignored while headings are scanned.
    """

    path = Path(source_path)
    normalized = _normalize_line_endings(markdown)
    raw_metadata, body = _split_front_matter(normalized, path)
    _validate_no_placeholders(normalized, path)
    metadata = _parse_metadata(raw_metadata, path)

    headings = _scan_headings(body, path)
    h1_headings = tuple(heading for heading in headings if heading.level == 1)
    if len(h1_headings) != 1:
        _fail(path, "expected exactly one level-one heading")

    title = h1_headings[0].title
    if title != metadata.title:
        _fail(path, "H1 title must match front-matter title exactly")

    sections = _parse_level_two_sections(body, headings, path)
    _validate_level_two_sections(sections, path)
    retrieval = _parse_retrieval(sections, body, headings, path)

    return CaseStudyDocument(
        source_path=path,
        metadata=metadata,
        title=title,
        sections=sections,
        retrieval=retrieval,
    )


def load_resume_entries(path: Path) -> dict[str, ResumeEntry]:
    try:
        markdown = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CaseStudyContractError(f"Unable to read resume source {path}: {exc}") from exc
    return parse_resume_entries(markdown, source_path=path)


def parse_resume_entries(
    markdown: str,
    *,
    source_path: Path | str = Path("<resume>"),
) -> dict[str, ResumeEntry]:
    """Read the existing resume entry metadata required for parent validation."""

    path = Path(source_path)
    normalized = _normalize_line_endings(markdown)
    entries: dict[str, ResumeEntry] = {}

    for match in _RESUME_ENTRY_PATTERN.finditer(normalized):
        metadata = _parse_resume_metadata(match.group("metadata"))
        entry_id = metadata.get("id")
        if not entry_id:
            continue
        if entry_id in entries:
            _fail(path, f"duplicate resume entry id: {entry_id}")

        section = metadata.get("section")
        if not section:
            _fail(path, f"resume entry {entry_id!r} is missing section")

        start_date = metadata.get("startDate")
        end_date = metadata.get("endDate")

        entries[entry_id] = ResumeEntry(
            id=entry_id,
            section=section,
            start_date=start_date,
            end_date=end_date,
        )

    if not entries:
        _fail(path, "no resume entry metadata found")
    return entries


def validate_case_study_collection(
    documents: Sequence[CaseStudyDocument],
    resume_entries: Mapping[str, ResumeEntry],
    *,
    expected_case_ids: set[str] | frozenset[str] | None = None,
) -> None:
    """Validate collection-level IDs and relationships to canonical resume entries."""

    errors: list[str] = []
    paths_by_id: dict[str, Path] = {}

    for document in documents:
        case_id = document.metadata.id
        previous_path = paths_by_id.get(case_id)
        if previous_path is not None:
            errors.append(
                f"duplicate case-study id {case_id!r}: {previous_path} and {document.source_path}"
            )
        else:
            paths_by_id[case_id] = document.source_path

        parent_id = document.metadata.parent_entry_id
        parent = resume_entries.get(parent_id)
        if parent is None:
            errors.append(
                f"{document.source_path}: parentEntryId {parent_id!r} is absent from resume"
            )
            continue

        if document.metadata.section != parent.section:
            errors.append(
                f"{document.source_path}: section {document.metadata.section!r} does not "
                f"match parent section {parent.section!r}"
            )

        date_error = _parent_date_error(document.metadata.date, parent)
        if date_error:
            errors.append(f"{document.source_path}: {date_error}")

    if expected_case_ids is not None:
        actual_ids = set(paths_by_id)
        missing = sorted(expected_case_ids - actual_ids)
        unexpected = sorted(actual_ids - expected_case_ids)
        if missing or unexpected:
            errors.append(
                "case-study collection differs from the expected source set; "
                f"missing={missing}, unexpected={unexpected}"
            )

    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise CaseStudyContractError(f"Case-study collection is invalid:\n{formatted}")


def load_case_study_collection(
    case_studies_directory: Path,
    resume_path: Path,
    *,
    expected_case_ids: set[str] | frozenset[str] | None = None,
) -> CaseStudyCollection:
    files = discover_case_study_files(case_studies_directory)
    documents = tuple(load_case_study(path) for path in files)
    resume_entries = load_resume_entries(resume_path)
    validate_case_study_collection(
        documents,
        resume_entries,
        expected_case_ids=expected_case_ids,
    )
    return CaseStudyCollection(documents=documents, resume_entries=resume_entries)


def normalize_section_slug(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    if not normalized:
        raise CaseStudyContractError(f"Unable to derive section slug from heading: {title!r}")
    return normalized


def _split_front_matter(markdown: str, path: Path) -> tuple[str, str]:
    if not markdown.startswith("---\n"):
        _fail(path, "file must start with YAML front matter")

    closing_marker = markdown.find("\n---\n", 4)
    if closing_marker < 0:
        _fail(path, "YAML front matter must end with a closing --- line")

    raw_metadata = markdown[4:closing_marker]
    body = markdown[closing_marker + 5 :].lstrip("\n")
    if not body.strip():
        _fail(path, "case-study body must not be empty")
    return raw_metadata, body


def _parse_metadata(raw_metadata: str, path: Path) -> CaseStudyMetadata:
    try:
        value = yaml.safe_load(raw_metadata)
    except yaml.YAMLError as exc:
        raise CaseStudyContractError(f"{path}: invalid YAML front matter: {exc}") from exc

    if not isinstance(value, dict):
        _fail(path, "YAML front matter must be a mapping")

    try:
        return CaseStudyMetadata.model_validate(value)
    except ValidationError as exc:
        messages = []
        for error in exc.errors(include_url=False):
            location = ".".join(str(part) for part in error["loc"])
            messages.append(f"{location}: {error['msg']}")
        _fail(path, "invalid front matter: " + "; ".join(messages))


def _scan_headings(body: str, path: Path) -> tuple[_Heading, ...]:
    headings: list[_Heading] = []
    fence_character: str | None = None
    fence_length = 0

    for line_index, line in enumerate(body.splitlines()):
        fence = _FENCE_PATTERN.match(line)
        if fence:
            marker = fence.group("marker")
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            continue

        if fence_character is not None:
            continue

        match = _HEADING_PATTERN.match(line)
        if not match:
            continue

        title = match.group("title").rstrip("#").rstrip()
        if not title:
            _fail(path, f"empty heading on line {line_index + 1}")
        headings.append(
            _Heading(
                level=len(match.group("marks")),
                title=title,
                line_index=line_index,
            )
        )

    return tuple(headings)


def _parse_level_two_sections(
    body: str,
    headings: Sequence[_Heading],
    path: Path,
) -> tuple[CaseStudySection, ...]:
    lines = body.splitlines()
    level_two = tuple(heading for heading in headings if heading.level == 2)
    if not level_two:
        _fail(path, "no level-two sections found")

    sections: list[CaseStudySection] = []
    seen_slugs: dict[str, str] = {}
    for index, heading in enumerate(level_two):
        end_line = level_two[index + 1].line_index if index + 1 < len(level_two) else len(lines)
        content = "\n".join(lines[heading.line_index + 1 : end_line]).strip()
        slug = normalize_section_slug(heading.title)
        previous = seen_slugs.get(slug)
        if previous is not None:
            _fail(
                path,
                f"duplicate normalized level-two section slug {slug!r}: "
                f"{previous!r} and {heading.title!r}",
            )
        seen_slugs[slug] = heading.title
        sections.append(CaseStudySection(title=heading.title, slug=slug, content=content))

    return tuple(sections)


def _validate_level_two_sections(
    sections: Sequence[CaseStudySection],
    path: Path,
) -> None:
    titles = tuple(section.title for section in sections)
    if titles[0] != "Overview":
        _fail(path, "first level-two section must be Overview")
    if titles[-1] != "Retrieval":
        _fail(path, "final level-two section must be Retrieval")

    missing = sorted(REQUIRED_LEVEL_TWO_SECTIONS - set(titles))
    if missing:
        _fail(path, f"missing required level-two sections: {missing}")

    for section in sections:
        if not section.content:
            _fail(path, f"section {section.title!r} must not be empty")


def _parse_retrieval(
    sections: Sequence[CaseStudySection],
    body: str,
    headings: Sequence[_Heading],
    path: Path,
) -> CaseStudyRetrieval:
    retrieval_section = next(section for section in sections if section.title == "Retrieval")
    retrieval_h2 = next(
        heading for heading in headings if heading.level == 2 and heading.title == "Retrieval"
    )

    h3_headings = tuple(heading for heading in headings if heading.level == 3)
    outside_retrieval = [
        heading.title for heading in h3_headings if heading.line_index <= retrieval_h2.line_index
    ]
    if outside_retrieval:
        _fail(path, f"level-three headings are only allowed in Retrieval: {outside_retrieval}")

    retrieval_headings = tuple(heading.title for heading in h3_headings)
    if retrieval_headings != RETRIEVAL_LEVEL_THREE_SECTIONS:
        _fail(
            path,
            "Retrieval must contain exactly these level-three sections in order: "
            + ", ".join(RETRIEVAL_LEVEL_THREE_SECTIONS),
        )

    parts = _split_level_three_sections(retrieval_section.content, path)
    hints = _parse_multiline_bullets(parts["Retrieval Hints"], path, "Retrieval Hints")
    primary_tags = _parse_tag_bullets(parts["Primary Tags"], path, "Primary Tags")
    secondary_tags = _parse_tag_bullets(
        parts["Secondary Tags"],
        path,
        "Secondary Tags",
        allow_empty=True,
    )

    if "case-study" not in primary_tags:
        _fail(path, "Primary Tags must include 'case-study'")

    overlap = sorted(set(primary_tags) & set(secondary_tags))
    if overlap:
        _fail(path, f"tags must not appear in both groups: {overlap}")

    return CaseStudyRetrieval(
        hints=hints,
        primary_tags=primary_tags,
        secondary_tags=secondary_tags,
    )


def _split_level_three_sections(text: str, path: Path) -> dict[str, str]:
    lines = text.splitlines()
    headings = tuple(heading for heading in _scan_headings(text, path) if heading.level == 3)

    parts: dict[str, str] = {}
    for index, heading in enumerate(headings):
        end_line = headings[index + 1].line_index if index + 1 < len(headings) else len(lines)
        content = "\n".join(lines[heading.line_index + 1 : end_line]).strip()
        parts[heading.title] = content
    return parts


def _parse_multiline_bullets(
    text: str,
    path: Path,
    label: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    bullets: list[list[str]] = []

    for line in text.splitlines():
        if line.startswith("- "):
            item = line[2:].strip()
            if not item:
                _fail(path, f"{label} contains an empty bullet")
            bullets.append([item])
            continue

        if not line.strip():
            continue
        if not bullets:
            _fail(path, f"{label} must contain only Markdown bullets")
        bullets[-1].append(line.strip())

    if not bullets and not allow_empty:
        _fail(path, f"{label} must contain at least one bullet")
    return tuple("\n".join(parts) for parts in bullets)


def _parse_tag_bullets(
    text: str,
    path: Path,
    label: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    values = _parse_multiline_bullets(text, path, label, allow_empty=allow_empty)
    normalized_values = tuple(value.casefold() for value in values)

    invalid = [value for value in values if not _SLUG_PATTERN.fullmatch(value)]
    if invalid:
        _fail(path, f"{label} must use lowercase kebab-case values: {invalid}")
    if len(normalized_values) != len(set(normalized_values)):
        _fail(path, f"duplicate values in {label}")
    return values


def _parse_resume_metadata(raw_metadata: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in raw_metadata.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip():
            metadata[key.strip()] = value.strip()
    return metadata


def _parent_date_error(case_date: str, parent: ResumeEntry) -> str | None:
    case_start = _date_value(case_date, end=False)
    case_end = _date_value(case_date, end=True)

    if parent.start_date is not None:
        if not _DATE_PATTERN.fullmatch(parent.start_date):
            return f"parent startDate has unsupported value {parent.start_date!r}"
        parent_start = _date_value(parent.start_date, end=False)
        if case_end < parent_start:
            return f"date {case_date!r} is earlier than parent startDate {parent.start_date!r}"

    if parent.end_date not in {None, "present"}:
        if not _DATE_PATTERN.fullmatch(parent.end_date):
            return f"parent endDate has unsupported value {parent.end_date!r}"
        parent_end = _date_value(parent.end_date, end=True)
        if case_start > parent_end:
            return f"date {case_date!r} is later than parent endDate {parent.end_date!r}"
    return None


def _date_value(value: str, *, end: bool) -> date:
    match = _DATE_PATTERN.fullmatch(value)
    if match is None:
        raise CaseStudyContractError(f"Invalid date in validated contract: {value!r}")
    year = int(match.group("year"))
    month_text = match.group("month")
    month = int(month_text) if month_text else (12 if end else 1)
    return date(year, month, 1)


def _validate_no_placeholders(markdown: str, path: Path) -> None:
    placeholders = [value for value in _KNOWN_PLACEHOLDERS if value in markdown]
    placeholders.extend(_ANGLE_PLACEHOLDER_PATTERN.findall(markdown))
    if placeholders:
        _fail(path, f"unresolved template placeholders: {sorted(set(placeholders))}")


def _validate_slug(value: str, *, field_name: str) -> None:
    if not _SLUG_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be lowercase kebab-case")


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _fail(path: Path, message: str) -> None:
    raise CaseStudyContractError(f"{path}: {message}")
