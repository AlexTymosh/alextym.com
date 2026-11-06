"""Transport-neutral application event emitted by the Chat streaming use case.

The event names and payload fields remain the existing Chat stream contract.
SSE framing belongs exclusively to the HTTP adapter in ``app.api.chat``.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChatStreamEvent:
    event: str
    data: dict[str, Any]
