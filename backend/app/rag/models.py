from dataclasses import dataclass, field
from typing import Any

from app.core.confidence import Confidence


@dataclass(frozen=True)
class RetrievalFilter:
    visibility: str = "public"
    topic_any: tuple[str, ...] = ()
    tag_any: tuple[str, ...] = ()
    section_any: tuple[str, ...] = ()

    @property
    def has_selectors(self) -> bool:
        return bool(self.topic_any or self.tag_any or self.section_any)


@dataclass(frozen=True)
class ChunkMetadata:
    source: str
    section: str
    topic: str
    visibility: str = "public"
    confidence: str = "self-reported"
    source_confidence: Confidence = "medium"
    tags: tuple[str, ...] = field(default_factory=tuple)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    content: str
    metadata: ChunkMetadata
