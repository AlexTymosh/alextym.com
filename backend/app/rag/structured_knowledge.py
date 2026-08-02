import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.confidence import Confidence
from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.rag.public_resume_source import get_public_resume_source_file

GENERATED_RESUME_CHUNKS_FILE = "resume.generated.chunks.json"
GENERATED_CASE_STUDY_CHUNKS_FILE = "case-studies.generated.chunks.json"
GENERATED_PUBLIC_KNOWLEDGE_CHUNKS_FILE = "public-knowledge.generated.chunks.json"
DEFAULT_GENERATED_RESUME_CHUNKS_PATH = Path(".tmp/rag/resume.generated.chunks.json")
DEFAULT_GENERATED_CHUNKS_PATH = DEFAULT_GENERATED_RESUME_CHUNKS_PATH
DEFAULT_GENERATED_KNOWLEDGE_PATH = Path(".tmp/rag/public-knowledge.generated.chunks.json")
SUPPORTED_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class GeneratedKnowledgeBundle:
    chunks: list[KnowledgeChunk]
    embedding_texts: list[str]
    source_files: tuple[str, ...]
    source_groups: tuple[str, ...]
    dataset_version: str


GeneratedResumeChunkBundle = GeneratedKnowledgeBundle


def load_generated_knowledge_chunks(
    chunks_path: Path | None = None,
) -> GeneratedKnowledgeBundle:
    resolved_path = chunks_path or _repository_root() / DEFAULT_GENERATED_KNOWLEDGE_PATH
    return _load_generated_chunks(
        resolved_path,
        missing_command="task rag:extract-public-knowledge",
    )


def load_generated_resume_chunks(
    chunks_path: Path | None = None,
) -> GeneratedKnowledgeBundle:
    """Load the legacy resume-only artifact during the staged migration."""

    resolved_path = chunks_path or _repository_root() / DEFAULT_GENERATED_RESUME_CHUNKS_PATH
    return _load_generated_chunks(
        resolved_path,
        missing_command="task rag:extract-resume",
    )


def _load_generated_chunks(
    resolved_path: Path,
    *,
    missing_command: str,
) -> GeneratedKnowledgeBundle:
    payload, raw_bytes = _load_json_payload(resolved_path, missing_command=missing_command)
    dataset_version = hashlib.sha256(raw_bytes).hexdigest()
    schema_version = _require_int(payload, "schema_version")

    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"Unsupported generated RAG schema version: {schema_version}")

    raw_chunks = _require_list(payload, "chunks")
    chunks: list[KnowledgeChunk] = []
    embedding_texts: list[str] = []
    chunk_ids: set[str] = set()

    for raw_chunk in raw_chunks:
        chunk_payload = _require_dict_value(raw_chunk, "chunk")
        knowledge_chunk, embedding_text = _chunk_from_payload(
            chunk_payload,
            schema_version=schema_version,
            dataset_version=dataset_version,
        )
        if knowledge_chunk.id in chunk_ids:
            raise ValueError(f"Duplicate generated RAG chunk id: {knowledge_chunk.id}")
        chunk_ids.add(knowledge_chunk.id)
        chunks.append(knowledge_chunk)
        embedding_texts.append(embedding_text)

    source_groups = _source_groups(payload, chunks)
    return GeneratedKnowledgeBundle(
        chunks=chunks,
        embedding_texts=embedding_texts,
        source_files=_source_files_for_replacement(payload, resolved_path=resolved_path),
        source_groups=source_groups,
        dataset_version=dataset_version,
    )


def _chunk_from_payload(
    chunk_payload: dict[str, Any],
    *,
    schema_version: int,
    dataset_version: str,
) -> tuple[KnowledgeChunk, str]:
    chunk_id = _require_text(chunk_payload, "id")
    content = _require_text(chunk_payload, "content")
    source = _require_dict(chunk_payload, "source")
    rag_payload = _require_dict(chunk_payload, "payload")
    vector_inputs = _require_dict(chunk_payload, "vector_inputs")
    embedding_text = _require_text(vector_inputs, "body_dense")
    source_title = _require_text(source, "title")
    source_file = _optional_text(source.get("path")) or get_public_resume_source_file()
    source_section = _require_text(source, "section")
    topic = _require_text(rag_payload, "topic")
    visibility = _require_text(rag_payload, "visibility")
    tags = _tuple_of_texts(rag_payload.get("tags", []))
    source_group = _source_group(chunk_id, rag_payload)
    document_type = _document_type(source_group, rag_payload)
    case_id = _optional_text(rag_payload.get("case_id"))
    case_section = _optional_text(rag_payload.get("case_section"))

    if source_group == "case-studies" and (not case_id or not case_section):
        raise ValueError(f"Generated case-study chunk is missing case metadata: {chunk_id}")

    metadata = ChunkMetadata(
        source=source_title,
        section=source_section,
        topic=topic,
        visibility=visibility,
        confidence=_optional_text(rag_payload.get("confidence")) or "self-reported",
        source_confidence=_source_confidence(rag_payload.get("source_confidence")),
        tags=tags,
        extra={
            "schema_version": schema_version,
            "source_file": source_file,
            "parent_id": _optional_text(chunk_payload.get("parent_id")),
            "source": source,
            "payload": rag_payload,
            "answer_facts": _list_of_texts(chunk_payload.get("answer_facts", [])),
            "retrieval_hints": _list_of_texts(chunk_payload.get("retrieval_hints", [])),
            "vector_inputs": vector_inputs,
            "retrieval": _optional_dict(chunk_payload.get("retrieval")),
            "document_type": document_type,
            "source_group": source_group,
            "case_id": case_id,
            "case_section": case_section,
            "organization": _optional_text(source.get("organization")),
            "dataset_version": dataset_version,
        },
    )

    chunk = KnowledgeChunk(id=chunk_id, content=content, metadata=metadata)
    return chunk, embedding_text


def _load_json_payload(
    path: Path,
    *,
    missing_command: str,
) -> tuple[dict[str, Any], bytes]:
    if not path.exists():
        raise FileNotFoundError(
            f"Generated RAG chunks file was not found: {path}. Run `{missing_command}` first."
        )

    raw_bytes = path.read_bytes()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Generated RAG chunks payload is invalid: {path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Generated RAG chunks payload must be a JSON object.")

    return payload, raw_bytes


def _source_files_for_replacement(
    payload: dict[str, Any],
    *,
    resolved_path: Path,
) -> tuple[str, ...]:
    explicit_source_files = payload.get("source_files")
    if explicit_source_files is not None:
        source_files = _required_list_of_texts(explicit_source_files, "source_files")
    else:
        source_files = [
            _optional_text(payload.get("source_path")) or get_public_resume_source_file()
        ]

    source_files.append(resolved_path.name)
    if _optional_text(payload.get("purpose")) == "public_knowledge_rag_extraction":
        source_files.extend(
            (
                GENERATED_RESUME_CHUNKS_FILE,
                GENERATED_CASE_STUDY_CHUNKS_FILE,
            )
        )
    return tuple(dict.fromkeys(source_files))


def _source_groups(
    payload: dict[str, Any],
    chunks: list[KnowledgeChunk],
) -> tuple[str, ...]:
    derived = tuple(
        dict.fromkeys(_require_extra_text(chunk.metadata.extra, "source_group") for chunk in chunks)
    )
    raw_groups = payload.get("source_groups")
    if raw_groups is None:
        return derived
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("Generated RAG field must be a non-empty list: source_groups")

    explicit: list[str] = []
    for raw_group in raw_groups:
        if not isinstance(raw_group, dict):
            raise ValueError("Generated RAG source_groups entries must be objects.")
        explicit.append(_require_text(raw_group, "id"))

    explicit_tuple = tuple(dict.fromkeys(explicit))
    if len(explicit_tuple) != len(explicit):
        raise ValueError("Generated RAG source_groups IDs must be unique.")
    if set(explicit_tuple) != set(derived):
        raise ValueError("Generated RAG source_groups do not match generated chunks.")
    return explicit_tuple


def _source_group(chunk_id: str, rag_payload: dict[str, Any]) -> str:
    if chunk_id.startswith("resume:"):
        expected = "resume"
    elif chunk_id.startswith("case:"):
        expected = "case-studies"
    else:
        raise ValueError(f"Unsupported generated RAG chunk ID: {chunk_id}")

    explicit = _optional_text(rag_payload.get("source_group"))
    if explicit and explicit != expected:
        raise ValueError(
            f"Generated RAG source_group {explicit!r} does not match chunk ID {chunk_id!r}."
        )
    return explicit or expected


def _document_type(source_group: str, rag_payload: dict[str, Any]) -> str:
    explicit = _optional_text(rag_payload.get("document_type"))
    expected = "case-study" if source_group == "case-studies" else "resume"
    if explicit and explicit != expected:
        raise ValueError(
            f"Generated RAG document_type {explicit!r} does not match source group "
            f"{source_group!r}."
        )
    return explicit or expected


def _require_extra_text(extra: dict[str, Any], key: str) -> str:
    value = _optional_text(extra.get(key))
    if not value:
        raise ValueError(f"Generated RAG chunk metadata is missing: {key}")
    return value


def _require_dict_value(raw_value: object, name: str) -> dict[str, Any]:
    if not isinstance(raw_value, dict):
        raise ValueError(f"Generated RAG {name} must be a JSON object.")
    return raw_value


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Generated RAG field must be an object: {key}")
    return value


def _optional_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _require_list(payload: dict[str, Any], key: str) -> list[object]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"Generated RAG field must be a list: {key}")
    return value


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = _optional_text(payload.get(key))
    if not value:
        raise ValueError(f"Generated RAG field must be a non-empty string: {key}")
    return value


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Generated RAG field must be an integer: {key}")
    return value


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    stripped_value = value.strip()
    return stripped_value or None


def _list_of_texts(value: object) -> list[str]:
    if not isinstance(value, list):
        return []

    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _required_list_of_texts(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"Generated RAG field must be a list: {field_name}")
    result = _list_of_texts(value)
    if len(result) != len(value) or not result:
        raise ValueError(f"Generated RAG field must contain only non-empty strings: {field_name}")
    return result


def _tuple_of_texts(value: object) -> tuple[str, ...]:
    return tuple(_list_of_texts(value))


def _source_confidence(value: object) -> Confidence:
    return value if value in {"low", "medium", "high"} else "medium"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]
