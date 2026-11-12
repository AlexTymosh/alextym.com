"""Transport-independent application events for an escalation stream.

The domain layer describes handoff state changes, not HTTP or SSE framing.
Only the API adapter decides which events become SSE fields and comments.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EscalationStreamEvent:
    kind: str
    payload: dict[str, Any]
    message_id: str | None = None


@dataclass(frozen=True)
class EscalationHeartbeat:
    """A liveness signal; its wire representation is transport-specific."""


EscalationStreamItem = EscalationStreamEvent | EscalationHeartbeat
