import json

from app.schemas.sse import ServerSentComment, ServerSentEvent, ServerSentStreamItem

SSE_MEDIA_TYPE = "text/event-stream"
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


def serialize_sse_item(item: ServerSentStreamItem) -> str:
    if isinstance(item, ServerSentComment):
        return f": {item.comment}\n\n"

    payload = json.dumps(item.data, ensure_ascii=False, separators=(",", ":"))
    lines = []
    if item.event_id:
        lines.append(f"id: {item.event_id}")
    lines.extend([f"event: {item.event}", f"data: {payload}"])
    return "\n".join(lines) + "\n\n"


def sse_event(
    event: str,
    data: dict[str, object],
    *,
    event_id: str | None = None,
) -> str:
    return serialize_sse_item(ServerSentEvent(event=event, data=dict(data), event_id=event_id))
