from functools import lru_cache
from pathlib import Path

from app.rag.models import ChunkMetadata
from app.rag.models import KnowledgeChunk
from app.rag.public_resume_source import get_public_resume_source_file_for_path
from app.rag.public_resume_source import get_public_resume_source_path
from app.rag.resume_rag_source import ResumeRagChunk
from app.rag.resume_rag_source import build_resume_rag_document
from app.rag.retriever import InMemoryRetriever

PLACEHOLDER_MARKER = "<!-- alextym:placeholder -->"


def load_public_knowledge(resume_source_path: Path | None = None) -> list[KnowledgeChunk]:
    source_path = get_public_resume_source_path(resume_source_path)
    if not source_path.exists():
        return []

    source_text = source_path.read_text(encoding="utf-8")
    if PLACEHOLDER_MARKER in source_text:
        return []

    document = build_resume_rag_document(
        source_text,
        source_path=get_public_resume_source_file_for_path(source_path),
    )
    return [
        _knowledge_chunk_from_resume_rag_chunk(chunk, source_file=document.source_path)
        for chunk in document.chunks
    ]


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


@lru_cache
def get_public_retriever() -> InMemoryRetriever:
    return InMemoryRetriever(load_public_knowledge())
