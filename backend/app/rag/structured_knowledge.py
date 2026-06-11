import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.rag.models import ChunkMetadata, KnowledgeChunk
from app.schemas.chat import Confidence

GENERATED_RESUME_CHUNKS_FILE = "resume.generated.chunks.json"
CANONICAL_RESUME_SOURCE_FILE = "content/public/resume.md"
PREVIOUS_CANONICAL_RESUME_SOURCE_FILE = "frontend/content/resume.md"
LEGACY_RESUME_SOURCE_FILE = "resume.md"
REPLACED_RESUME_SOURCE_FILES = (
    CANONICAL_RESUME_SOURCE_FILE,
    PREVIOUS_CANONICAL_RESUME_SOURCE_FILE,
    LEGACY_RESUME_SOURCE_FILE,
    GENERATED_RESUME_CHUNKS_FILE,
)
DEFAULT_GENERATED_CHUNKS_PATH = Path(".tmp/rag/resume.generated.chunks.json")
SUPPORTED_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class GeneratedResumeChunkBundle:
    chunks: list[KnowledgeChunk]
    embedding_texts: list[str]
    source_files: tuple[str, ...]


def load_generated_resume_chunks(
    chunks_path: Path | None = None,
) -> GeneratedResumeChunkBundle:
    resolved_path = chunks_path or _repository_root() / DEFAULT_GENERATED_CHUNKS_PATH
    payload = _load_json_payload(resolved_path)
    schema_version = _require_int(payload, "schema_version")

    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"Unsupported generated RAG schema version: {schema_version}")

    raw_chunks = _require_list(payload, "chunks")
    chunks: list[KnowledgeChunk] = []
    embedding_texts: list[str] = []

    for raw_chunk in raw_chunks:
        chunk_payload = _require_dict_value(raw_chunk, "chunk")
        knowledge_chunk, embedding_text = _chunk_from_payload(
            chunk_payload,
            schema_version=schema_version,
        )
        chunks.append(knowledge_chunk)
        embedding_texts.append(embedding_text)

    return GeneratedResumeChunkBundle(
        chunks=chunks,
        embedding_texts=embedding_texts,
        source_files=REPLACED_RESUME_SOURCE_FILES,
    )


def _chunk_from_payload(
    chunk_payload: dict[str, Any],
    *,
    schema_version: int,
) -> tuple[KnowledgeChunk, str]:
    chunk_id = _require_text(chunk_payload, "id")
    content = _require_text(chunk_payload, "content")
    source = _require_dict(chunk_payload, "source")
    rag_payload = _require_dict(chunk_payload, "payload")
    vector_inputs = _require_dict(chunk_payload, "vector_inputs")
    embedding_text = _require_text(vector_inputs, "body_dense")
    source_title = _require_text(source, "title")
    source_file = _optional_text(source.get("path")) or CANONICAL_RESUME_SOURCE_FILE
    source_section = _require_text(source, "section")
    topic = _require_text(rag_payload, "topic")
    visibility = _require_text(rag_payload, "visibility")
    tags = _tuple_of_texts(rag_payload.get("tags", []))

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
        },
    )

    chunk = KnowledgeChunk(id=chunk_id, content=content, metadata=metadata)
    return chunk, embedding_text


def _load_json_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Generated RAG chunks file was not found: {path}. Run `task rag:extract-resume` first."
        )

    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)

    if not isinstance(payload, dict):
        raise ValueError("Generated RAG chunks payload must be a JSON object.")

    return payload


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


def _tuple_of_texts(value: object) -> tuple[str, ...]:
    return tuple(_list_of_texts(value))


def _source_confidence(value: object) -> Confidence:
    return value if value in {"low", "medium", "high"} else "medium"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]
