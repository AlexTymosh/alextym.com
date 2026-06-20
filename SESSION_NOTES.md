# SESSION_NOTES.md

Purpose: execute behaviour-preserving architecture refactors from the current boundary audit.

## Constraints

- Work one step at a time.
- Do not change user-visible behaviour unless the active step explicitly requires it.
- Do not restyle UI during architecture refactors.
- Do not rename public routes, request schemas, response schemas, or environment variables unless the active step explicitly requires it.
- Prefer moving code before rewriting code.
- After each step, update the table status.
- Status values: `todo`, `in_progress`, `blocked`, `done`.
- If blocked, record the exact blocker in the `Notes` column.

## Validation commands

Primary:

```bash
task ci
```

Fallback when `task` is unavailable:

```bash
cd backend && python -m pytest
cd frontend && npm run lint
```

## Execution table

| Step | Area | Status | Target files | Required action | Validation | Notes |
|---:|---|---|---|---|---|---|
| 1 | Backend tests | done | `backend/tests/test_chat.py` | Split chat endpoint tests by behaviour area. Keep production code unchanged. | `task ci` | |
| 2 | Backend chat | done | `backend/app/services/chat.py` | Extract pre-RAG policy and language helpers. Preserve response payloads. | `task ci` | |
| 3 | Backend chat | done | `backend/app/services/chat.py` | Extract intent resolution and follow-up routing helpers. Preserve routing behaviour. | `task ci` | |
| 4 | Backend chat/RAG | done | `backend/app/services/chat.py` | Extract confidence scoring helpers. Preserve confidence labels. | `task ci` | |
| 5 | Backend API/SSE | done | `backend/app/services/chat.py`, `backend/app/services/escalation.py`, `backend/app/api/*` | Add shared SSE serialization helper and remove service-owned SSE formatting. | `task ci` | |
| 6 | Handoff copy | done | `backend/app/services/escalation.py`, `backend/app/services/telegram_webhook.py` | Centralise shared handoff quick-reply copy. Remove duplication. | `task ci` | |
| 7 | Handoff notifier | todo | `backend/app/services/escalation.py` | Move notifier protocol, noop notifier, Telegram notifier, and Telegram message builders into separate modules. | `task ci` | |
| 8 | Handoff sessions | todo | `backend/app/services/escalation_sessions.py` | Separate session state transitions from Redis persistence. Store should not accept API schema objects. | `task ci` | |
| 9 | Handoff API | todo | `backend/app/api/escalation.py`, `backend/app/services/escalation.py` | Remove duplicated availability gate from API. Keep business rule in service. | `task ci` | |
| 10 | Rate limit | todo | `backend/app/services/rate_limit.py`, `backend/app/api/rate_limit.py` | Move client identity extraction out of service layer. Remove FastAPI import from service module. | `task ci` | |
| 11 | RAG/schema | todo | `backend/app/schemas/chat.py`, `backend/app/rag/qdrant_store.py` | Move `Confidence` type to a neutral module and update imports. | `task ci` | |
| 12 | RAG adapter | todo | `backend/app/rag/qdrant_retriever.py`, RAG store fakes/tests | Remove `inspect.signature()` capability detection. Standardise store `search()` contract. | `task ci` | |
| 13 | Telegram tests | todo | `backend/tests/test_telegram_webhook.py` | Split webhook tests by auth, replies, callbacks, close, and errors. | `task ci` | |
| 14 | Frontend stream | todo | `frontend/components/chat-shell.tsx` | Extract stream text renderer and handoff EventSource lifecycle into dedicated modules/hooks. | `task ci` | |
| 15 | Frontend controller | todo | `frontend/components/chat-shell.tsx` | Move chat state machine and submit flow to controller hook. Keep component render-focused. | `task ci` | |
| 16 | Frontend utilities | todo | `frontend/lib/chat-state.ts` | Split chat-state utilities by concern after controller extraction. | `task ci` | |

## Commit order

1. Test split before risky backend chat extraction.
2. Backend chat helper extraction.
3. SSE and handoff shared copy extraction.
4. Handoff service/session boundary cleanup.
5. Infrastructure/RAG boundary cleanup.
6. Telegram test split.
7. Frontend stream/controller/rendering cleanup.

## Stop conditions

- Stop if `task ci` fails after a move-only refactor.
- Stop if public API response JSON changes unexpectedly.
- Stop if frontend chat/handoff behaviour changes without an explicit requirement.
- Stop if a refactor requires schema or environment variable changes not listed in the active step.
