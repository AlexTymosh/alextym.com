from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from app.rag.case_study_contract import (
    CaseStudyCollection,
    CaseStudyDocument,
    CaseStudySection,
    load_case_study_collection,
)

DEFAULT_CASE_STUDIES_DIRECTORY = Path("content/public/case-studies")
DEFAULT_RESUME_PATH = Path("content/public/resume.md")
DEFAULT_JSON_OUTPUT_PATH = Path(".tmp/rag/case-studies.generated.chunks.json")
DEFAULT_PREVIEW_OUTPUT_PATH = Path(".tmp/human-readable-preview/case-studies-rag-preview.md")

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

_LIST_ITEM_PATTERN = re.compile(r"^[ \t]*[-*+][ \t]+(?P<content>.+?)\s*$")
_RAW_URL_PATTERN = re.compile(
    r"(?P<url>https?://[^\s<>()]+|www\.[^\s<>()]+)",
    re.IGNORECASE,
)
_MARKDOWN_LINK_TOKEN = "]("


@dataclass(frozen=True)
class CaseStudySourceReference:
    path: str
    id: str
    title: str
    section: str
    organization: str
    date: str
    parent_entry_id: str
    case_section: str
    case_section_title: str
    location: str | None = None
    links: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CaseStudyChunkPayload:
    topic: str
    visibility: str
    confidence: str
    source_confidence: str
    document_type: str
    source_group: str
    case_id: str
    case_section: str
    parent_entry_id: str
    retrieval_priority: str
    primary_tags: tuple[str, ...]
    secondary_tags: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class CaseStudyRagChunk:
    id: str
    parent_id: str
    source: CaseStudySourceReference
    payload: CaseStudyChunkPayload
    answer_facts: tuple[str, ...]
    retrieval_hints: tuple[str, ...]
    content: str
    vector_inputs: dict[str, str]
    retrieval: dict[str, Any]


@dataclass(frozen=True)
class CaseStudyRagDocument:
    source_directory: str
    resume_path: str
    chunks: tuple[CaseStudyRagChunk, ...] = field(default_factory=tuple)


def load_case_study_rag_document(
    *,
    case_studies_directory: Path,
    resume_path: Path,
    repository_root: Path | None = None,
    expected_case_ids: set[str] | frozenset[str] | None = None,
) -> CaseStudyRagDocument:
    collection = load_case_study_collection(
        case_studies_directory,
        resume_path,
        expected_case_ids=expected_case_ids,
    )
    return build_case_study_rag_document(
        collection,
        case_studies_directory=case_studies_directory,
        resume_path=resume_path,
        repository_root=repository_root,
    )


def build_case_study_rag_document(
    collection: CaseStudyCollection,
    *,
    case_studies_directory: Path,
    resume_path: Path,
    repository_root: Path | None = None,
) -> CaseStudyRagDocument:
    root = (repository_root or _repository_root()).resolve()
    chunks: list[CaseStudyRagChunk] = []

    for document in sorted(collection.documents, key=lambda item: item.metadata.id):
        for section in document.answer_sections:
            chunks.append(_build_chunk(document, section, repository_root=root))

    generated = CaseStudyRagDocument(
        source_directory=_portable_path(case_studies_directory, root),
        resume_path=_portable_path(resume_path, root),
        chunks=tuple(chunks),
    )
    _validate_generated_document(
        generated,
        expected_case_ids={document.metadata.id for document in collection.documents},
    )
    return generated


def render_case_study_rag_json(document: CaseStudyRagDocument) -> str:
    payload = {
        "schema_version": 2,
        "source_directory": document.source_directory,
        "resume_path": document.resume_path,
        "purpose": "case_study_rag_extraction",
        "chunks": [asdict(chunk) for chunk in document.chunks],
    }
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def render_case_study_rag_preview(document: CaseStudyRagDocument) -> str:
    lines = [
        "# Case Studies RAG Preview",
        "",
        "<!-- generated from validated canonical case-study markdown -->",
        "<!-- this file is a human-readable preview, not an embedding source -->",
        f"<!-- source_directory: {document.source_directory} -->",
        f"<!-- resume_path: {document.resume_path} -->",
        "",
    ]

    for chunk in document.chunks:
        lines.extend(
            [
                f"## {chunk.source.title} — {chunk.source.case_section_title}",
                "",
                f"- id: {chunk.id}",
                f"- parent_id: {chunk.parent_id}",
                f"- source_path: {chunk.source.path}",
                f"- case_id: {chunk.payload.case_id}",
                f"- case_section: {chunk.payload.case_section}",
                f"- parent_entry_id: {chunk.payload.parent_entry_id}",
                f"- organization: {chunk.source.organization}",
                f"- date: {chunk.source.date}",
                f"- retrieval_priority: {chunk.payload.retrieval_priority}",
                f"- primary_tags: {', '.join(chunk.payload.primary_tags)}",
                f"- secondary_tags: {', '.join(chunk.payload.secondary_tags)}",
                "",
                "### Content",
                "",
                chunk.content,
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

        if chunk.source.links:
            lines.extend(
                [
                    "### Source Links",
                    "",
                    *_format_bullets(chunk.source.links),
                    "",
                ]
            )

    return "\n".join(lines).strip() + "\n"


def write_case_study_rag_outputs(
    *,
    case_studies_directory: Path,
    resume_path: Path,
    json_output_path: Path,
    preview_output_path: Path,
    repository_root: Path | None = None,
    expected_case_ids: set[str] | frozenset[str] | None = None,
) -> CaseStudyRagDocument:
    document = load_case_study_rag_document(
        case_studies_directory=case_studies_directory,
        resume_path=resume_path,
        repository_root=repository_root,
        expected_case_ids=expected_case_ids,
    )

    _write_text_atomic(json_output_path, render_case_study_rag_json(document))
    _write_text_atomic(preview_output_path, render_case_study_rag_preview(document))
    return document


def main(argv: list[str] | None = None) -> None:
    repository_root = _repository_root()
    parser = argparse.ArgumentParser(
        description="Extract deterministic semantic RAG chunks from public case studies.",
    )
    parser.add_argument(
        "--case-studies",
        default=str(repository_root / DEFAULT_CASE_STUDIES_DIRECTORY),
        help="Directory containing canonical **/*.case.md sources.",
    )
    parser.add_argument(
        "--resume",
        default=str(repository_root / DEFAULT_RESUME_PATH),
        help="Canonical resume source used for parent-entry validation.",
    )
    parser.add_argument(
        "--json-output",
        default=str(repository_root / DEFAULT_JSON_OUTPUT_PATH),
        help="Generated structured chunks JSON output path.",
    )
    parser.add_argument(
        "--preview-output",
        default=str(repository_root / DEFAULT_PREVIEW_OUTPUT_PATH),
        help="Human-readable preview output path inside .tmp.",
    )
    args = parser.parse_args(argv)

    json_output_path = Path(args.json_output)
    preview_output_path = Path(args.preview_output)
    document = write_case_study_rag_outputs(
        case_studies_directory=Path(args.case_studies),
        resume_path=Path(args.resume),
        json_output_path=json_output_path,
        preview_output_path=preview_output_path,
        repository_root=repository_root,
    )

    _print_extraction_summary(
        chunk_count=len(document.chunks),
        case_count=len({chunk.payload.case_id for chunk in document.chunks}),
        json_output_path=json_output_path,
        preview_output_path=preview_output_path,
    )


def _build_chunk(
    document: CaseStudyDocument,
    section: CaseStudySection,
    *,
    repository_root: Path,
) -> CaseStudyRagChunk:
    content, answer_facts, content_links = _normalize_section_content(section.content)
    retrieval_hints, hint_links = _normalize_retrieval_hints(document.retrieval.hints)
    links = _unique_preserving_order((*content_links, *hint_links))

    metadata = document.metadata
    all_tags = tuple(sorted({*document.retrieval.primary_tags, *document.retrieval.secondary_tags}))
    parent_id = f"case:{metadata.id}"
    chunk_id = f"{parent_id}:{section.slug}"
    topic = f"{metadata.id.removeprefix('case-')}-{section.slug}"

    source = CaseStudySourceReference(
        path=_portable_path(document.source_path, repository_root),
        id=metadata.id,
        title=document.title,
        section=metadata.section,
        organization=metadata.organization,
        date=metadata.date,
        parent_entry_id=metadata.parent_entry_id,
        case_section=section.slug,
        case_section_title=section.title,
        location=metadata.location,
        links=links,
    )
    payload = CaseStudyChunkPayload(
        topic=topic,
        visibility="public",
        confidence="self-reported",
        source_confidence="medium",
        document_type=metadata.document_type,
        source_group="case-studies",
        case_id=metadata.id,
        case_section=section.slug,
        parent_entry_id=metadata.parent_entry_id,
        retrieval_priority=metadata.retrieval_priority,
        primary_tags=document.retrieval.primary_tags,
        secondary_tags=document.retrieval.secondary_tags,
        tags=all_tags,
    )
    vector_inputs = _build_vector_inputs(
        source=source,
        payload=payload,
        content=content,
        retrieval_hints=retrieval_hints,
    )
    _assert_clean_vector_inputs(vector_inputs)

    return CaseStudyRagChunk(
        id=chunk_id,
        parent_id=parent_id,
        source=source,
        payload=payload,
        answer_facts=answer_facts,
        retrieval_hints=retrieval_hints,
        content=content,
        vector_inputs=vector_inputs,
        retrieval={
            "modes": RETRIEVAL_MODES,
            "named_vectors": NAMED_VECTORS,
            "parent_id": parent_id,
            "payload_filter_fields": (
                "payload.document_type",
                "payload.source_group",
                "payload.case_id",
                "payload.case_section",
                "payload.primary_tags",
                "payload.secondary_tags",
                "source.section",
            ),
        },
    )


def _normalize_section_content(markdown: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    logical_blocks: list[tuple[str, bool]] = []
    links: list[str] = []
    active_bullet: list[str] | None = None
    active_paragraph: list[str] = []

    def flush_bullet() -> None:
        nonlocal active_bullet
        if active_bullet is None:
            return
        value = " ".join(part for part in active_bullet if part).strip()
        if value:
            logical_blocks.append((value, True))
        active_bullet = None

    def flush_paragraph() -> None:
        if not active_paragraph:
            return
        value = " ".join(part for part in active_paragraph if part).strip()
        if value:
            logical_blocks.append((value, False))
        active_paragraph.clear()

    for raw_line in markdown.splitlines():
        if not raw_line.strip():
            flush_bullet()
            flush_paragraph()
            continue

        list_item = _LIST_ITEM_PATTERN.match(raw_line)
        if list_item:
            flush_bullet()
            flush_paragraph()
            text, found_links = _strip_links_and_urls(list_item.group("content"))
            links.extend(found_links)
            active_bullet = [text]
            continue

        text, found_links = _strip_links_and_urls(raw_line.strip())
        links.extend(found_links)
        if active_bullet is not None and raw_line[:1].isspace():
            active_bullet.append(text)
        else:
            flush_bullet()
            active_paragraph.append(text)

    flush_bullet()
    flush_paragraph()

    if not logical_blocks:
        raise ValueError("Case-study answer section produced no content.")

    rendered = "\n\n".join(
        f"- {value}" if is_bullet else value for value, is_bullet in logical_blocks
    )
    answer_facts = tuple(value for value, _ in logical_blocks)
    return rendered, answer_facts, _unique_preserving_order(links)


def _normalize_retrieval_hints(
    hints: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    normalized: list[str] = []
    links: list[str] = []
    for hint in hints:
        text, found_links = _strip_links_and_urls(hint.replace("\n", " "))
        if text:
            normalized.append(text)
        links.extend(found_links)
    return tuple(normalized), _unique_preserving_order(links)


def _strip_links_and_urls(text: str) -> tuple[str, tuple[str, ...]]:
    without_markdown, markdown_links = _replace_markdown_links(text)
    raw_links: list[str] = []

    def remove_raw_url(match: re.Match[str]) -> str:
        raw_links.append(match.group("url"))
        return ""

    cleaned = _RAW_URL_PATTERN.sub(remove_raw_url, without_markdown)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned).strip()
    return cleaned, _unique_preserving_order((*markdown_links, *raw_links))


def _replace_markdown_links(text: str) -> tuple[str, tuple[str, ...]]:
    output: list[str] = []
    links: list[str] = []
    cursor = 0

    while cursor < len(text):
        open_label = text.find("[", cursor)
        if open_label < 0:
            output.append(text[cursor:])
            break

        close_label = _find_unescaped(text, "]", open_label + 1)
        if close_label < 0 or close_label + 1 >= len(text) or text[close_label + 1] != "(":
            output.append(text[cursor : open_label + 1])
            cursor = open_label + 1
            continue

        close_target = _find_balanced_parenthesis(text, close_label + 1)
        if close_target < 0:
            output.append(text[cursor : open_label + 1])
            cursor = open_label + 1
            continue

        label = text[open_label + 1 : close_label]
        target = text[close_label + 2 : close_target].strip()
        url = _markdown_link_target(target)

        output.append(text[cursor:open_label])
        output.append(label)
        if url:
            links.append(url)
        cursor = close_target + 1

    return "".join(output), _unique_preserving_order(links)


def _find_unescaped(text: str, needle: str, start: int) -> int:
    index = start
    while True:
        index = text.find(needle, index)
        if index < 0:
            return -1
        if index == 0 or text[index - 1] != "\\":
            return index
        index += 1


def _find_balanced_parenthesis(text: str, open_index: int) -> int:
    depth = 0
    escaped = False
    for index in range(open_index, len(text)):
        character = text[index]
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _markdown_link_target(target: str) -> str:
    if not target:
        return ""
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")].strip()
    return target.split(maxsplit=1)[0].strip()


def _build_vector_inputs(
    *,
    source: CaseStudySourceReference,
    payload: CaseStudyChunkPayload,
    content: str,
    retrieval_hints: Sequence[str],
) -> dict[str, str]:
    title = f"{source.title} — {source.case_section_title}"
    hints_text = _format_bullets_text(retrieval_hints)
    keyword_text = " ".join((*payload.tags, payload.case_section))
    summary = _join_non_empty(
        [
            title,
            source.organization,
            source.location,
            source.date,
            content,
            hints_text,
        ]
    )

    return {
        "title_dense": title,
        "body_dense": _join_non_empty([title, content, hints_text]),
        "summary_dense": summary,
        "keywords_sparse": keyword_text,
        "rerank_text": summary,
        "compression_text": content,
    }


def _validate_generated_document(
    document: CaseStudyRagDocument,
    *,
    expected_case_ids: set[str],
) -> None:
    chunk_ids = [chunk.id for chunk in document.chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Generated case-study chunk IDs must be unique.")

    actual_case_ids = {chunk.payload.case_id for chunk in document.chunks}
    if actual_case_ids != expected_case_ids:
        raise ValueError(
            "Generated case-study chunks do not represent the validated source set; "
            f"missing={sorted(expected_case_ids - actual_case_ids)}, "
            f"unexpected={sorted(actual_case_ids - expected_case_ids)}"
        )

    for chunk in document.chunks:
        if chunk.payload.case_section == "retrieval":
            raise ValueError("Retrieval metadata must not become an answer chunk.")
        if not chunk.content.strip():
            raise ValueError(f"Generated chunk has empty content: {chunk.id}")
        if chunk.parent_id != f"case:{chunk.payload.case_id}":
            raise ValueError(f"Generated chunk has an invalid parent ID: {chunk.id}")
        for name, value in chunk.vector_inputs.items():
            if not value.strip():
                raise ValueError(f"Generated chunk has empty vector input {name!r}: {chunk.id}")


def _assert_clean_vector_inputs(vector_inputs: dict[str, str]) -> None:
    for key, value in vector_inputs.items():
        lowered = value.casefold()
        if (
            _MARKDOWN_LINK_TOKEN in value
            or "http://" in lowered
            or "https://" in lowered
            or "www." in lowered
        ):
            raise ValueError(f"Vector input contains a Markdown link or URL: {key}")


def _portable_path(path: Path, repository_root: Path) -> str:
    try:
        return path.resolve().relative_to(repository_root).as_posix()
    except ValueError:
        return path.as_posix()


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(content, encoding="utf-8", newline="\n")
    temporary_path.replace(path)


def _unique_preserving_order(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _format_bullets(items: Sequence[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _format_bullets_text(items: Sequence[str]) -> str:
    return "\n".join(_format_bullets(items))


def _join_non_empty(values: Sequence[str | None]) -> str:
    return "\n\n".join(value.strip() for value in values if value and value.strip())


def _print_extraction_summary(
    *,
    chunk_count: int,
    case_count: int,
    json_output_path: Path,
    preview_output_path: Path,
) -> None:
    print(
        f"{_label('OK', '32')} Extracted {chunk_count} semantic chunk(s) "
        f"from {case_count} case study source(s)."
    )
    print(f"{_label('JSON', '36')} {json_output_path}")
    print(f"{_label('PREVIEW', '36')} {preview_output_path}")
    print(
        f"{_label('NEXT', '33')} Review the generated JSON before combining "
        "it with public knowledge or sending it to embeddings."
    )


def _label(text: str, colour_code: str) -> str:
    return _colour(f"[{text}]", colour_code)


def _colour(text: str, colour_code: str) -> str:
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return text
    return f"\033[{colour_code}m{text}\033[0m"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


if __name__ == "__main__":
    main()
