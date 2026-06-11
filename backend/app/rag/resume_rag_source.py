import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SUMMARY_RAG_MARKER = "## RAG"
ENTRY_RAG_MARKER = "### RAG"
DEFAULT_SOURCE_PATH = Path("content/public/resume.md")
DEFAULT_JSON_OUTPUT_PATH = Path(".tmp/rag/resume.generated.chunks.json")
DEFAULT_PREVIEW_OUTPUT_PATH = Path(".tmp/human-readable-preview/resume-rag-preview.md")

BLOCK_SPLIT_PATTERN = re.compile(r"\n(?=## )")
MARKDOWN_LINK_PATTERN = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)$")
URL_PATTERN = re.compile(r"https?://|(?:^|\s)/[A-Za-z0-9_./-]+")
TAG_CHARACTER_PATTERN = re.compile(r"[^a-z0-9]+")

RAG_SUBSECTIONS = {
    "answer facts": "answer_facts",
    "retrieval hints": "retrieval_hints",
    "primary tags": "primary_tags",
    "secondary tags": "secondary_tags",
}

RETRIEVAL_MODES = (
    "dense",
    "sparse",
    "hybrid",
    "rerank",
    "multi_query",
    "parent_child",
    "context_compression",
)

NAMED_VECTORS = (
    "title_dense",
    "body_dense",
    "summary_dense",
    "keywords_sparse",
)


@dataclass(frozen=True)
class SourceReference:
    path: str
    id: str
    title: str
    title_url: str | None
    section: str
    organization: str | None = None
    organization_url: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class ChunkPayload:
    topic: str
    visibility: str
    confidence: str
    source_confidence: str
    primary_tags: tuple[str, ...]
    secondary_tags: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ResumeRagChunk:
    id: str
    parent_id: str
    source: SourceReference
    payload: ChunkPayload
    answer_facts: tuple[str, ...]
    retrieval_hints: tuple[str, ...]
    content: str
    vector_inputs: dict[str, str]
    retrieval: dict[str, Any]


@dataclass(frozen=True)
class ResumeRagDocument:
    source_path: str
    chunks: tuple[ResumeRagChunk, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ParsedRagSection:
    answer_facts: tuple[str, ...]
    retrieval_hints: tuple[str, ...]
    primary_tags: tuple[str, ...]
    secondary_tags: tuple[str, ...]


def build_resume_rag_document(
    markdown: str,
    *,
    source_path: str = str(DEFAULT_SOURCE_PATH),
) -> ResumeRagDocument:
    normalized_markdown = _normalize_line_endings(markdown)
    chunks: list[ResumeRagChunk] = []

    summary_rag = _extract_summary_rag(normalized_markdown)
    if summary_rag:
        chunks.append(
            _build_chunk(
                source_path=source_path,
                source_id="summary",
                source_title="Summary",
                source_section="summary",
                title="Summary",
                rag_text=summary_rag,
            )
        )

    for entry in _extract_entry_rag_sections(normalized_markdown):
        chunks.append(
            _build_chunk(
                source_path=source_path,
                source_id=entry.metadata["id"],
                source_title=entry.title,
                source_section=entry.metadata["section"],
                title=entry.title,
                rag_text=entry.rag_text,
                start_date=entry.metadata.get("startDate"),
                end_date=entry.metadata.get("endDate"),
                organization=entry.metadata.get("organization"),
                location=entry.metadata.get("location"),
            )
        )

    return ResumeRagDocument(source_path=source_path, chunks=tuple(chunks))


def render_resume_rag_json(document: ResumeRagDocument) -> str:
    payload = {
        "schema_version": 2,
        "source_path": document.source_path,
        "purpose": "resume_rag_extraction",
        "chunks": [asdict(chunk) for chunk in document.chunks],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def render_resume_rag_preview(document: ResumeRagDocument) -> str:
    lines = [
        "# Resume RAG Preview",
        "",
        "<!-- generated from canonical resume markdown -->",
        "<!-- this file is a human-readable preview, not an embedding source -->",
        f"<!-- source_path: {document.source_path} -->",
        "",
    ]

    for chunk in document.chunks:
        lines.extend(
            [
                f"## {chunk.source.title}",
                "",
                f"- id: {chunk.id}",
                f"- parent_id: {chunk.parent_id}",
                f"- source_id: {chunk.source.id}",
                f"- source_section: {chunk.source.section}",
                f"- topic: {chunk.payload.topic}",
                f"- visibility: {chunk.payload.visibility}",
                f"- source_confidence: {chunk.payload.source_confidence}",
                f"- primary_tags: {', '.join(chunk.payload.primary_tags)}",
                f"- secondary_tags: {', '.join(chunk.payload.secondary_tags)}",
                "",
                "### Answer Facts",
                "",
                *_format_bullets(chunk.answer_facts),
                "",
            ]
        )

        if chunk.retrieval_hints:
            lines.extend(
                [
                    "### Retrieval Hints",
                    "",
                    *_format_bullets(chunk.retrieval_hints),
                    "",
                ]
            )

    return "\n".join(lines).strip() + "\n"


def write_resume_rag_outputs(
    *,
    source_path: Path,
    json_output_path: Path,
    preview_output_path: Path,
) -> ResumeRagDocument:
    source_text = source_path.read_text(encoding="utf-8")
    document = build_resume_rag_document(
        source_text,
        source_path=_relative_path(source_path),
    )

    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    preview_output_path.parent.mkdir(parents=True, exist_ok=True)

    json_output_path.write_text(render_resume_rag_json(document), encoding="utf-8")
    preview_output_path.write_text(
        render_resume_rag_preview(document),
        encoding="utf-8",
    )

    return document


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Extract RAG-only resume sections from canonical resume.md.",
    )
    parser.add_argument(
        "--source",
        default=str(_repository_root() / DEFAULT_SOURCE_PATH),
        help="Canonical resume markdown source path.",
    )
    parser.add_argument(
        "--json-output",
        default=str(_repository_root() / DEFAULT_JSON_OUTPUT_PATH),
        help="Generated structured chunks JSON output path.",
    )
    parser.add_argument(
        "--preview-output",
        default=str(_repository_root() / DEFAULT_PREVIEW_OUTPUT_PATH),
        help="Human-readable preview output path inside .tmp.",
    )
    args = parser.parse_args(argv)

    json_output_path = Path(args.json_output)
    preview_output_path = Path(args.preview_output)
    document = write_resume_rag_outputs(
        source_path=Path(args.source),
        json_output_path=json_output_path,
        preview_output_path=preview_output_path,
    )

    _print_extraction_summary(
        chunk_count=len(document.chunks),
        json_output_path=json_output_path,
        preview_output_path=preview_output_path,
    )


def _print_extraction_summary(
    *,
    chunk_count: int,
    json_output_path: Path,
    preview_output_path: Path,
) -> None:
    print(f"{_label('OK', '32')} Extracted {chunk_count} RAG chunk(s).")
    print(f"{_label('JSON', '36')} {json_output_path}")
    print(f"{_label('PREVIEW', '36')} {preview_output_path}")
    print(
        f"{_label('NEXT', '33')} Review the generated JSON before sending "
        f"it to embeddings: {json_output_path}"
    )


def _label(text: str, colour_code: str) -> str:
    return _colour(f"[{text}]", colour_code)


def _colour(text: str, colour_code: str) -> str:
    if os.environ.get("NO_COLOR"):
        return text
    if os.environ.get("TERM") == "dumb":
        return text

    return f"\033[{colour_code}m{text}\033[0m"


@dataclass(frozen=True)
class _EntryRagSection:
    title: str
    metadata: dict[str, str]
    rag_text: str


@dataclass(frozen=True)
class _MarkdownLink:
    text: str
    url: str | None


def _extract_summary_rag(markdown: str) -> str | None:
    summary = _extract_required_section(markdown, "# Summary", ["# Entries"])
    return _extract_optional_section(summary, SUMMARY_RAG_MARKER, ["# Entries"])


def _extract_entry_rag_sections(markdown: str) -> list[_EntryRagSection]:
    entries_markdown = _extract_required_section(
        markdown,
        "# Entries",
        ["# Additional Sections"],
    )
    entries: list[_EntryRagSection] = []

    for block in _split_entry_blocks(entries_markdown):
        metadata_block = _extract_yaml_metadata_block(block)
        metadata = _parse_metadata(metadata_block)
        rag_text = _extract_optional_section(
            block,
            ENTRY_RAG_MARKER,
            ["\n## ", "\n# Additional Sections"],
        )

        if not rag_text:
            continue

        entries.append(
            _EntryRagSection(
                title=metadata.get("title") or _extract_entry_title(block),
                metadata=metadata,
                rag_text=rag_text,
            )
        )

    return entries


def _build_chunk(
    *,
    source_path: str,
    source_id: str,
    source_title: str,
    source_section: str,
    title: str,
    rag_text: str,
    start_date: str | None = None,
    end_date: str | None = None,
    organization: str | None = None,
    location: str | None = None,
) -> ResumeRagChunk:
    parsed_rag = _parse_rag_section(rag_text)
    title_link = _parse_markdown_link(title or source_title)
    organization_link = _parse_markdown_link(organization)
    topic = _slug(source_id or title_link.text or source_section)
    all_tags = tuple(sorted({*parsed_rag.primary_tags, *parsed_rag.secondary_tags}))

    source = SourceReference(
        path=source_path,
        id=source_id,
        title=title_link.text,
        title_url=title_link.url,
        section=source_section,
        organization=organization_link.text if organization else None,
        organization_url=organization_link.url if organization else None,
        location=location,
        start_date=start_date,
        end_date=end_date,
    )
    payload = ChunkPayload(
        topic=topic,
        visibility="public",
        confidence="self-reported",
        source_confidence="medium",
        primary_tags=parsed_rag.primary_tags,
        secondary_tags=parsed_rag.secondary_tags,
        tags=all_tags,
    )
    parent_id = f"resume:{source_id}"
    chunk_id = f"{parent_id}:rag"
    content = _format_bullets_text(parsed_rag.answer_facts)

    vector_inputs = _build_vector_inputs(
        source=source,
        payload=payload,
        answer_facts=parsed_rag.answer_facts,
        retrieval_hints=parsed_rag.retrieval_hints,
    )
    _assert_clean_vector_inputs(vector_inputs)

    return ResumeRagChunk(
        id=chunk_id,
        parent_id=parent_id,
        source=source,
        payload=payload,
        answer_facts=parsed_rag.answer_facts,
        retrieval_hints=parsed_rag.retrieval_hints,
        content=content,
        vector_inputs=vector_inputs,
        retrieval={
            "modes": RETRIEVAL_MODES,
            "named_vectors": NAMED_VECTORS,
            "parent_id": parent_id,
            "payload_filter_fields": (
                "payload.topic",
                "payload.visibility",
                "payload.primary_tags",
                "payload.secondary_tags",
                "source.section",
            ),
        },
    )


def _parse_rag_section(rag_text: str) -> ParsedRagSection:
    subsections = _split_rag_subsections(rag_text)

    if not subsections:
        answer_facts = tuple(_parse_bullets(rag_text))
        tags = _fallback_tags(answer_facts)
        return ParsedRagSection(
            answer_facts=answer_facts,
            retrieval_hints=(),
            primary_tags=tags,
            secondary_tags=(),
        )

    answer_facts = tuple(_parse_bullets(subsections.get("answer_facts", "")))
    retrieval_hints = tuple(_parse_bullets(subsections.get("retrieval_hints", "")))
    primary_tags = _parse_tags(subsections.get("primary_tags", ""))
    secondary_tags = _parse_tags(subsections.get("secondary_tags", ""))

    if not answer_facts:
        raise ValueError("Structured RAG section must include Answer Facts.")
    if not primary_tags:
        raise ValueError("Structured RAG section must include Primary Tags.")

    _validate_answer_facts(answer_facts)

    return ParsedRagSection(
        answer_facts=answer_facts,
        retrieval_hints=retrieval_hints,
        primary_tags=primary_tags,
        secondary_tags=secondary_tags,
    )


def _split_rag_subsections(rag_text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_key: str | None = None

    for line in rag_text.splitlines():
        heading = re.match(r"^####\s+(.+?)\s*$", line.strip())
        if heading:
            normalized_heading = heading.group(1).casefold().strip()
            current_key = RAG_SUBSECTIONS.get(normalized_heading)
            if current_key:
                sections.setdefault(current_key, [])
            continue

        if current_key:
            sections[current_key].append(line)

    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


def _validate_answer_facts(answer_facts: tuple[str, ...]) -> None:
    meta_patterns = (
        "relevant to questions about",
        "this experience is relevant",
        "this role is relevant",
        "this training is relevant",
    )

    for fact in answer_facts:
        normalized_fact = fact.casefold()
        if any(pattern in normalized_fact for pattern in meta_patterns):
            raise ValueError("Answer Facts must contain answerable facts, not retrieval hints.")


def _build_vector_inputs(
    *,
    source: SourceReference,
    payload: ChunkPayload,
    answer_facts: tuple[str, ...],
    retrieval_hints: tuple[str, ...],
) -> dict[str, str]:
    title = source.title
    organization = source.organization
    period = _format_period(source.start_date, source.end_date)
    facts_text = _format_bullets_text(answer_facts)
    hints_text = _format_bullets_text(retrieval_hints)
    keyword_text = " ".join(payload.tags)

    return {
        "title_dense": title,
        "body_dense": _join_non_empty([title, facts_text, hints_text]),
        "summary_dense": _join_non_empty(
            [title, organization, source.location, period, facts_text, hints_text]
        ),
        "keywords_sparse": keyword_text,
        "rerank_text": _join_non_empty(
            [title, organization, source.location, period, facts_text, hints_text]
        ),
        "compression_text": facts_text,
    }


def _assert_clean_vector_inputs(vector_inputs: dict[str, str]) -> None:
    for key, value in vector_inputs.items():
        if MARKDOWN_LINK_PATTERN.search(value) or URL_PATTERN.search(value):
            raise ValueError(f"Vector input contains markdown link or URL: {key}")


def _extract_required_section(
    text: str,
    start_marker: str,
    end_markers: list[str],
) -> str:
    section = _extract_optional_section(text, start_marker, end_markers)
    if section is None:
        raise ValueError(f"Markdown section is missing: {start_marker}")
    return section


def _extract_optional_section(
    text: str,
    start_marker: str,
    end_markers: list[str],
) -> str | None:
    start_index = text.find(start_marker)
    if start_index == -1:
        return None

    content_start = start_index + len(start_marker)
    end_index = len(text)

    for marker in end_markers:
        marker_index = text.find(marker, content_start)
        if marker_index != -1:
            end_index = min(end_index, marker_index)

    content = text[content_start:end_index].strip()
    return content or None


def _split_entry_blocks(entries_markdown: str) -> list[str]:
    return [
        block.strip()
        for block in BLOCK_SPLIT_PATTERN.split(entries_markdown.strip())
        if block.strip().startswith("## ")
    ]


def _extract_yaml_metadata_block(block: str) -> str:
    match = re.search(r"```yaml\n([\s\S]*?)\n```", block)
    if not match:
        raise ValueError("Resume entry metadata block is missing.")
    return match.group(1)


def _parse_metadata(metadata_block: str) -> dict[str, str]:
    metadata: dict[str, str] = {}

    for raw_line in metadata_block.splitlines():
        line = raw_line.strip()
        match = re.match(r"^([a-zA-Z]+):\s*(.*)$", line)
        if match:
            metadata[match.group(1)] = match.group(2).strip()

    for required_key in ("id", "section", "title"):
        if not metadata.get(required_key):
            raise ValueError(f"Resume metadata field is missing: {required_key}")

    return metadata


def _extract_entry_title(block: str) -> str:
    first_line = block.strip().splitlines()[0]
    return first_line.removeprefix("## ").strip()


def _parse_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    active_bullet = ""

    for raw_line in text.strip().splitlines():
        line = raw_line.strip()

        if not line or line.startswith("<!--"):
            continue

        if line.startswith("- "):
            if active_bullet:
                bullets.append(active_bullet.strip())
            active_bullet = line[2:].strip()
            continue

        if active_bullet:
            active_bullet = f"{active_bullet} {line}"

    if active_bullet:
        bullets.append(active_bullet.strip())

    return bullets


def _parse_tags(text: str) -> tuple[str, ...]:
    tags = [_slug(tag) for tag in _parse_bullets(text)]
    unique_tags = sorted({tag for tag in tags if tag})

    return tuple(unique_tags)


def _fallback_tags(answer_facts: tuple[str, ...]) -> tuple[str, ...]:
    text = " ".join(answer_facts).casefold()
    detected_tags = [
        tag
        for tag in ("automation", "python", "fastapi", "api", "excel", "sql")
        if re.search(rf"\b{re.escape(tag)}\b", text)
    ]

    return tuple(sorted(set(detected_tags or ["resume"])))


def _parse_markdown_link(value: str | None) -> _MarkdownLink:
    if not value:
        return _MarkdownLink(text="", url=None)

    stripped_value = value.strip()
    match = MARKDOWN_LINK_PATTERN.match(stripped_value)
    if not match:
        return _MarkdownLink(text=stripped_value, url=None)

    return _MarkdownLink(text=match.group(1).strip(), url=match.group(2).strip())


def _slug(value: str) -> str:
    slug = TAG_CHARACTER_PATTERN.sub("-", value.casefold()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def _format_bullets(items: tuple[str, ...]) -> list[str]:
    return [f"- {item}" for item in items]


def _format_bullets_text(items: tuple[str, ...]) -> str:
    return "\n".join(_format_bullets(items))


def _join_non_empty(values: list[str | None]) -> str:
    return "\n\n".join(value.strip() for value in values if value and value.strip())


def _format_period(start_date: str | None, end_date: str | None) -> str | None:
    if not start_date and not end_date:
        return None
    return f"{start_date or 'unknown'} - {end_date or 'present'}"


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repository_root()).as_posix()
    except ValueError:
        return path.as_posix()


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


if __name__ == "__main__":
    main()
