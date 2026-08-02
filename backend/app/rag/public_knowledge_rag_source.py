from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.rag.case_study_rag_source import (
    DEFAULT_CASE_STUDIES_DIRECTORY,
    CaseStudyRagDocument,
    load_case_study_rag_document,
)
from app.rag.resume_rag_source import ResumeRagDocument, build_resume_rag_document

DEFAULT_RESUME_PATH = Path("content/public/resume.md")
DEFAULT_JSON_OUTPUT_PATH = Path(".tmp/rag/public-knowledge.generated.chunks.json")
DEFAULT_PREVIEW_OUTPUT_PATH = Path(".tmp/human-readable-preview/public-knowledge-rag-preview.md")
SUPPORTED_SCHEMA_VERSION = 2
REQUIRED_VECTOR_INPUTS = (
    "title_dense",
    "body_dense",
    "summary_dense",
    "keywords_sparse",
    "rerank_text",
    "compression_text",
)


@dataclass(frozen=True)
class PublicKnowledgeSourceGroup:
    id: str
    document_type: str
    source_files: tuple[str, ...]
    chunk_count: int


@dataclass(frozen=True)
class PublicKnowledgeRagDocument:
    source_files: tuple[str, ...]
    source_groups: tuple[PublicKnowledgeSourceGroup, ...]
    chunks: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def load_public_knowledge_rag_document(
    *,
    resume_path: Path,
    case_studies_directory: Path,
    repository_root: Path | None = None,
    expected_case_ids: set[str] | frozenset[str] | None = None,
) -> PublicKnowledgeRagDocument:
    root = (repository_root or _repository_root()).resolve()
    resume_source_file = _portable_path(resume_path, root)
    resume_document = build_resume_rag_document(
        resume_path.read_text(encoding="utf-8"),
        source_path=resume_source_file,
    )
    case_study_document = load_case_study_rag_document(
        case_studies_directory=case_studies_directory,
        resume_path=resume_path,
        repository_root=root,
        expected_case_ids=expected_case_ids,
    )
    return build_public_knowledge_rag_document(
        resume_document,
        case_study_document,
    )


def build_public_knowledge_rag_document(
    resume_document: ResumeRagDocument,
    case_study_document: CaseStudyRagDocument,
) -> PublicKnowledgeRagDocument:
    resume_chunks = tuple(asdict(chunk) for chunk in resume_document.chunks)
    case_study_chunks = tuple(asdict(chunk) for chunk in case_study_document.chunks)
    chunks = (*resume_chunks, *case_study_chunks)

    resume_source_files = _source_files(resume_chunks)
    case_study_source_files = _source_files(case_study_chunks)
    source_groups = (
        PublicKnowledgeSourceGroup(
            id="resume",
            document_type="resume",
            source_files=resume_source_files,
            chunk_count=len(resume_chunks),
        ),
        PublicKnowledgeSourceGroup(
            id="case-studies",
            document_type="case-study",
            source_files=case_study_source_files,
            chunk_count=len(case_study_chunks),
        ),
    )
    document = PublicKnowledgeRagDocument(
        source_files=_unique_preserving_order((*resume_source_files, *case_study_source_files)),
        source_groups=source_groups,
        chunks=chunks,
    )
    _validate_public_knowledge_document(document)
    return document


def render_public_knowledge_rag_json(document: PublicKnowledgeRagDocument) -> str:
    payload = {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "purpose": "public_knowledge_rag_extraction",
        "source_files": document.source_files,
        "source_groups": [asdict(group) for group in document.source_groups],
        "chunks": document.chunks,
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


def render_public_knowledge_rag_preview(document: PublicKnowledgeRagDocument) -> str:
    lines = [
        "# Public Knowledge RAG Preview",
        "",
        "<!-- generated from canonical resume and case-study sources -->",
        "<!-- this file is a human-readable preview, not an embedding source -->",
        f"<!-- schema_version: {SUPPORTED_SCHEMA_VERSION} -->",
        f"<!-- chunks: {len(document.chunks)} -->",
        "",
    ]

    chunks_by_group = {
        "resume": tuple(chunk for chunk in document.chunks if _chunk_group(chunk) == "resume"),
        "case-studies": tuple(
            chunk for chunk in document.chunks if _chunk_group(chunk) == "case-studies"
        ),
    }
    for group in document.source_groups:
        lines.extend(
            [
                f"## {group.id}",
                "",
                f"- document_type: {group.document_type}",
                f"- chunk_count: {group.chunk_count}",
                f"- source_files: {', '.join(group.source_files)}",
                "",
            ]
        )
        for chunk in chunks_by_group[group.id]:
            source = _require_mapping(chunk, "source")
            payload = _require_mapping(chunk, "payload")
            lines.extend(
                [
                    f"### {_require_text(source, 'title')}",
                    "",
                    f"- id: {_require_text(chunk, 'id')}",
                    f"- parent_id: {_require_text(chunk, 'parent_id')}",
                    f"- source_path: {_require_text(source, 'path')}",
                    f"- section: {_require_text(source, 'section')}",
                    f"- topic: {_require_text(payload, 'topic')}",
                    "",
                    _require_text(chunk, "content"),
                    "",
                ]
            )

    return "\n".join(lines).strip() + "\n"


def write_public_knowledge_rag_outputs(
    *,
    resume_path: Path,
    case_studies_directory: Path,
    json_output_path: Path,
    preview_output_path: Path,
    repository_root: Path | None = None,
    expected_case_ids: set[str] | frozenset[str] | None = None,
) -> PublicKnowledgeRagDocument:
    document = load_public_knowledge_rag_document(
        resume_path=resume_path,
        case_studies_directory=case_studies_directory,
        repository_root=repository_root,
        expected_case_ids=expected_case_ids,
    )
    _write_text_atomic(json_output_path, render_public_knowledge_rag_json(document))
    _write_text_atomic(preview_output_path, render_public_knowledge_rag_preview(document))
    return document


def main(argv: list[str] | None = None) -> None:
    repository_root = _repository_root()
    parser = argparse.ArgumentParser(
        description="Build one deterministic public-knowledge artifact from resume and cases.",
    )
    parser.add_argument(
        "--resume",
        default=str(repository_root / DEFAULT_RESUME_PATH),
        help="Canonical public resume markdown source.",
    )
    parser.add_argument(
        "--case-studies",
        default=str(repository_root / DEFAULT_CASE_STUDIES_DIRECTORY),
        help="Directory containing canonical **/*.case.md sources.",
    )
    parser.add_argument(
        "--json-output",
        default=str(repository_root / DEFAULT_JSON_OUTPUT_PATH),
        help="Unified generated public-knowledge JSON output path.",
    )
    parser.add_argument(
        "--preview-output",
        default=str(repository_root / DEFAULT_PREVIEW_OUTPUT_PATH),
        help="Human-readable unified preview output path inside .tmp.",
    )
    args = parser.parse_args(argv)

    json_output_path = Path(args.json_output)
    preview_output_path = Path(args.preview_output)
    document = write_public_knowledge_rag_outputs(
        resume_path=Path(args.resume),
        case_studies_directory=Path(args.case_studies),
        json_output_path=json_output_path,
        preview_output_path=preview_output_path,
        repository_root=repository_root,
    )
    _print_extraction_summary(
        document=document,
        json_output_path=json_output_path,
        preview_output_path=preview_output_path,
    )


def _validate_public_knowledge_document(document: PublicKnowledgeRagDocument) -> None:
    if tuple(group.id for group in document.source_groups) != ("resume", "case-studies"):
        raise ValueError("Generated public knowledge must contain resume and case-studies groups.")

    expected_count = sum(group.chunk_count for group in document.source_groups)
    if expected_count != len(document.chunks):
        raise ValueError("Generated public-knowledge group counts do not match chunk count.")
    if any(group.chunk_count <= 0 for group in document.source_groups):
        raise ValueError("Generated public-knowledge source groups must not be empty.")

    chunk_ids: list[str] = []
    derived_source_files: list[str] = []
    group_counts = {"resume": 0, "case-studies": 0}

    for chunk in document.chunks:
        chunk_id = _require_text(chunk, "id")
        chunk_ids.append(chunk_id)
        group = _chunk_group(chunk)
        group_counts[group] += 1

        source = _require_mapping(chunk, "source")
        derived_source_files.append(_require_text(source, "path"))
        _require_text(chunk, "parent_id")
        _require_text(chunk, "content")

        vector_inputs = _require_mapping(chunk, "vector_inputs")
        for vector_name in REQUIRED_VECTOR_INPUTS:
            _require_text(vector_inputs, vector_name)

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Generated public-knowledge chunk IDs must be unique.")
    if group_counts != {group.id: group.chunk_count for group in document.source_groups}:
        raise ValueError("Generated public-knowledge chunks do not match source-group counts.")
    if document.source_files != _unique_preserving_order(derived_source_files):
        raise ValueError("Generated public-knowledge source files are inconsistent with chunks.")


def _chunk_group(chunk: Mapping[str, Any]) -> str:
    chunk_id = _require_text(chunk, "id")
    if chunk_id.startswith("resume:"):
        return "resume"
    if chunk_id.startswith("case:"):
        return "case-studies"
    raise ValueError(f"Unsupported generated public-knowledge chunk ID: {chunk_id}")


def _source_files(chunks: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return _unique_preserving_order(
        _require_text(_require_mapping(chunk, "source"), "path") for chunk in chunks
    )


def _require_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"Generated public-knowledge field must be an object: {key}")
    return value


def _require_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Generated public-knowledge field must be non-empty text: {key}")
    return value.strip()


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


def _print_extraction_summary(
    *,
    document: PublicKnowledgeRagDocument,
    json_output_path: Path,
    preview_output_path: Path,
) -> None:
    group_counts = ", ".join(f"{group.id}={group.chunk_count}" for group in document.source_groups)
    print(
        f"{_label('OK', '32')} Extracted {len(document.chunks)} public-knowledge "
        f"chunk(s) ({group_counts})."
    )
    print(f"{_label('JSON', '36')} {json_output_path}")
    print(f"{_label('PREVIEW', '36')} {preview_output_path}")
    print(
        f"{_label('NEXT', '33')} Review the unified artifact before enabling "
        "public-knowledge ingestion."
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
