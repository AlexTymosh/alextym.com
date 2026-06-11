from functools import lru_cache
from pathlib import Path

from app.rag.models import ChunkMetadata
from app.rag.models import KnowledgeChunk
from app.rag.resume_rag_source import DEFAULT_SOURCE_PATH
from app.rag.resume_rag_source import ResumeRagChunk
from app.rag.resume_rag_source import build_resume_rag_document
from app.rag.retriever import InMemoryRetriever

PLACEHOLDER_MARKER = "<!-- alextym:placeholder -->"
CANONICAL_RESUME_SOURCE_PATH = DEFAULT_SOURCE_PATH


def load_public_knowledge(resume_source_path: Path | None = None) -> list[KnowledgeChunk]:
    source_path = _resolve_resume_source_path(resume_source_path)
    if not source_path.exists():
        return []

    source_text = source_path.read_text(encoding="utf-8")
    if PLACEHOLDER_MARKER in source_text:
        return []

    document = build_resume_rag_document(
        source_text,
        source_path=_relative_path(source_path),
    )
    return [
        _knowledge_chunk_from_resume_rag_chunk(chunk, source_file=document.source_path)
        for chunk in document.chunks
    ]


def _resolve_resume_source_path(resume_source_path: Path | None) -> Path:
    if resume_source_path is None:
        return _repository_root() / CANONICAL_RESUME_SOURCE_PATH
    if resume_source_path.is_dir():
        return resume_source_path / "resume.md"
    return resume_source_path


def _knowledge_chunk_from_resume_rag_chunk(
    chunk: ResumeRagChunk,
    *,
    source_file: str,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk.id,
        content=chunk.content,
        metadata=ChunkMetadata(
            source=chunk.source.title,
            section=chunk.source.section,
            topic=chunk.payload.topic,
            visibility=chunk.payload.visibility,
            confidence=chunk.payload.confidence,
            source_confidence=chunk.payload.source_confidence,
            tags=chunk.payload.tags,
            extra={
                "source_file": source_file,
                "parent_id": chunk.parent_id,
                "source": {
                    "path": chunk.source.path,
                    "id": chunk.source.id,
                    "title": chunk.source.title,
                    "title_url": chunk.source.title_url,
                    "section": chunk.source.section,
                    "organization": chunk.source.organization,
                    "organization_url": chunk.source.organization_url,
                    "location": chunk.source.location,
                    "start_date": chunk.source.start_date,
                    "end_date": chunk.source.end_date,
                },
                "payload": {
                    "topic": chunk.payload.topic,
                    "visibility": chunk.payload.visibility,
                    "confidence": chunk.payload.confidence,
                    "source_confidence": chunk.payload.source_confidence,
                    "primary_tags": list(chunk.payload.primary_tags),
                    "secondary_tags": list(chunk.payload.secondary_tags),
                    "tags": list(chunk.payload.tags),
                },
                "answer_facts": list(chunk.answer_facts),
                "retrieval_hints": list(chunk.retrieval_hints),
                "vector_inputs": chunk.vector_inputs,
                "retrieval": chunk.retrieval,
            },
        ),
    )


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(_repository_root()).as_posix()
    except ValueError:
        return path.as_posix()


@lru_cache
def get_public_retriever() -> InMemoryRetriever:
    return InMemoryRetriever(load_public_knowledge())
