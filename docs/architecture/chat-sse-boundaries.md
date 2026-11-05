# Chat streaming — application events and SSE boundary

**Step 08 (2026-11-05):** Keep application stream events distinct from HTTP/SSE
wire framing, without changing Chat behaviour or the existing public routes.

## Ownership

- `app.domain.chat_stream.ChatStreamEvent` is the transport-neutral event type.
- `app.services.chat.ChatService` yields those events; `app.services.chat_metrics`
  observes them without importing SSE schemas.
- `app.api.chat` converts each event into the existing SSE representation using
  `app.api.sse.sse_event`. Headers and the endpoint remain unchanged.
- `app.schemas.sse.ServerSentEvent` and its serializer remain available to
  other consumers, including escalation streams.

## Preserved contracts

- `POST /api/chat/stream`: HTTP 200, `text/event-stream`, existing no-cache and
  buffering headers, existing error redaction.
- Event sequence and payload: `meta`, zero or more `token`, `sources`, `done`
  on successful responses. Errors still use the existing `error` event.
- No new Chat `id:` SSE fields, infrastructure, dependencies or configuration.
- `/api/chat` JSON response, RAG, stream safety buffers, escalation/Telegram,
  cancellation checks and instrumentation retain their existing behaviour.
- Application `ChatStreamEvent` intentionally retains the existing logical
  event names and JSON payload structure; only SSE framing is decoupled.

## Verification

Run the focused tests in `backend/tests/test_chat_stream_boundary.py`,
`test_chat_stream_endpoint.py`, `test_chat_real_streaming.py`, and existing
Chat/RAG, Escalation, SSE, and browser regression tests via `task ci`.

Known limitations: this stage does not change the synchronous RAG/LLM execution
inside the asynchronous stream or the Redis escalation read-modify-write race.
Do not claim those runtime risks are resolved by a transport-only refactor.
