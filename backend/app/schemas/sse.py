from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ServerSentEvent:
    event: str
    data: dict[str, Any]
    event_id: str | None = None


@dataclass(frozen=True)
class ServerSentComment:
    comment: str


ServerSentStreamItem = ServerSentEvent | ServerSentComment
