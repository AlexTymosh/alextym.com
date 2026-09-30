# Session Notes

## Issue #107: preserve owner messages after handoff

Branch: `codex/107-owner-chat-context`.

The user approved three commits, committed Step 1 as `68434d4`, and authorized
continuing to Step 2. Step 2 is implemented and awaits user review and a user-created
commit. Do not start Step 3 without the user's next instruction. Do not commit or
push on their behalf.

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

### Step 2 completed: frontend history and transcript

- Map visible `alex` replies to API `owner` entries in AI history and repeat-handoff
  transcripts. Keep UI sender labels and the live handoff SSE role unchanged.
- Include owner messages in the existing count, per-message, and total character limits.
- Add 14 pure history/transcript checks to the existing Playwright runner, covering
  speaker order, unchanged UI data, ordinary chat, blank text, clipping, and newest-message limits.
- Update API, architecture, and RAG documentation to describe frontend transmission.
- Synced local dependencies with the existing lockfile before final verification.
- `npm run lint`, `npm run typecheck`, and `npm run build`: passed with Next.js 16.3.4.
- Focused `chat-history.spec.ts` checks: 14 passed using the Chromium project and one worker.
  These tests exercise pure functions, not a browser conversation or live providers.
- The initial focused run finished its tests but stalled while stopping the managed Next.js
  server on Windows. It was interrupted; its server process is no longer running. The successful
  rerun set `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000` to skip the unnecessary managed server;
  these pure tests make no requests to that URL.
- `git diff --check` and the repository raw-Cyrillic check passed.
- Full browser scenarios and repository-wide CI remain part of Step 3.

### Remaining agreed step

3. End-to-end regression coverage for manual/automatic close, streaming/JSON fallback,
   and repeat handoff; final documentation and CI checks. Issue #107 remains open until
   this verification is complete.
