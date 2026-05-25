from functools import lru_cache
from pathlib import Path

from app.rag.chunker import chunk_markdown
from app.rag.models import KnowledgeChunk
from app.rag.retriever import InMemoryRetriever

PLACEHOLDER_MARKER = "<!-- alextym:placeholder -->"
PUBLIC_KNOWLEDGE_FILES = ("resume.md",)


def load_public_knowledge(knowledge_dir: Path | None = None) -> list[KnowledgeChunk]:
    knowledge_root = knowledge_dir or Path(__file__).resolve().parents[2] / "knowledge"
    chunks: list[KnowledgeChunk] = []

    for file_name in PUBLIC_KNOWLEDGE_FILES:
        file_path = knowledge_root / file_name
        if not file_path.exists():
            continue

        file_text = file_path.read_text(encoding="utf-8")
        if PLACEHOLDER_MARKER in file_text:
            continue

        chunks.extend(chunk_markdown(file_text, source=file_name))

    return chunks


@lru_cache
def get_public_retriever() -> InMemoryRetriever:
    return InMemoryRetriever(load_public_knowledge())
