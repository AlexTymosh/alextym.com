from dataclasses import dataclass, field

from app.schemas.chat import Confidence


@dataclass(frozen=True)
class ChunkMetadata:
    source: str
    section: str
    topic: str
    visibility: str = "public"
    confidence: str = "self-reported"
    source_confidence: Confidence = "medium"
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    content: str
    metadata: ChunkMetadata
