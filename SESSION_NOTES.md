# Session Notes

## Issue #107: preserve owner messages after handoff

Branch: `codex/107-owner-chat-context`.

The user approved three commits and requested Step 1 only. Step 1 is implemented
and awaits user review and a user-created commit. Do not start Step 2 or Step 3
without the user's next instruction. Do not commit or push on their behalf.

### Step 1 completed: backend contract and context

- Accept `owner` alongside `user` and `assistant` in chat history and handoff transcripts.
- Preserve speaker identity in contextualization, answer prompts, temporary sessions,
  and Telegram transcript text. Owner messages remain untrusted context, not facts or instructions.
- Resolve ambiguous references to owner replies; ask for clarification when unresolved.
- Prevent owner replies and handoff-close/expiry notices from confirming an old handoff offer.
- Add regression tests and update API, RAG, and security documentation.
- `task backend:check`: passed, 509 tests. One earlier run had an intermittent failure in
  the existing Redis probe timeout test (`SET`); the complete rerun passed without Redis changes.
- Existing Starlette/httpx deprecation warning remains. Tests used local provider doubles;
  live OpenAI, Qdrant, Telegram, and browser end-to-end behaviour were not verified.

### Remaining agreed steps

2. Frontend: map visible `alex` messages to API `owner` entries in AI history and repeat-handoff
   transcripts, preserving ordering and size limits; add frontend checks.
3. End-to-end regression coverage for manual/automatic close, streaming/JSON fallback,
   and repeat handoff; final documentation and CI checks.

The frontend is unchanged in Step 1, so issue #107 is not ready to close yet.
