import hashlib
import re

from app.rag.models import ChunkMetadata, KnowledgeChunk

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
NON_TOPIC_CHARACTER_PATTERN = re.compile(r"[^a-z0-9]+")


def chunk_markdown(
    markdown_text: str,
    *,
    source: str,
    max_words: int = 700,
    overlap_words: int = 100,
) -> list[KnowledgeChunk]:
    if max_words < 50:
        raise ValueError("max_words must be at least 50.")
    if overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("overlap_words must be non-negative and smaller than max_words.")

    chunks: list[KnowledgeChunk] = []

    for section, section_text in _split_into_sections(markdown_text):
        normalized_text = _normalize_markdown_text(section_text)
        if not normalized_text:
            continue

        for index, content in enumerate(_split_words(normalized_text, max_words, overlap_words)):
            chunks.append(
                KnowledgeChunk(
                    id=_chunk_id(source, section, index, content),
                    content=content,
                    metadata=ChunkMetadata(
                        source=source,
                        section=section,
                        topic=_topic_from_section(section),
                        visibility="public",
                        confidence="self-reported",
                        source_confidence="medium",
                    ),
                )
            )

    return chunks


def _split_into_sections(markdown_text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_section = "Document"
    current_lines: list[str] = []

    for line in markdown_text.splitlines():
        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            _append_section(sections, current_section, current_lines)
            current_section = heading_match.group(2).strip()
            current_lines = []
            continue

        current_lines.append(line)

    _append_section(sections, current_section, current_lines)
    return sections


def _append_section(
    sections: list[tuple[str, str]],
    section: str,
    lines: list[str],
) -> None:
    text = "\n".join(lines).strip()
    if text:
        sections.append((section, text))


def _normalize_markdown_text(markdown_text: str) -> str:
    paragraphs = [
        " ".join(line.strip() for line in paragraph.splitlines() if line.strip())
        for paragraph in re.split(r"\n\s*\n", markdown_text)
    ]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _split_words(text: str, max_words: int, overlap_words: int) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap_words

    return chunks


def _topic_from_section(section: str) -> str:
    normalized_section = NON_TOPIC_CHARACTER_PATTERN.sub("-", section.lower()).strip("-")
    return normalized_section or "document"


def _chunk_id(source: str, section: str, index: int, content: str) -> str:
    digest = hashlib.sha256(f"{source}:{section}:{index}:{content}".encode("utf-8")).hexdigest()
    return digest[:16]
