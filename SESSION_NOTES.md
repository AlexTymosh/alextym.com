# Chat stream terminal-error work

Last updated: 2026-08-28

Branch: `codex/fix-chat-stream-terminal-errors`

GitHub issue: `#106` - `P1: Handle chat stream errors and incomplete stream termination`

## Work boundary

This branch is for fixing the chat UI behaviour when `POST /api/chat/stream`
fails or ends without the normal `done` event. Keep changes scoped to:

- frontend chat stream parsing and terminal-state handling;
- chat controller behaviour for SSE `error`, incomplete streams, and JSON
  fallback;
- focused Playwright coverage for failed and incomplete chat streams;
- API/chat documentation that records the terminal stream contract.

Do not change RAG retrieval, Qdrant ingestion, production environment variables,
deployment settings, Telegram handoff behaviour, or unrelated UI flows. Do not
push the branch or open a pull request without explicit approval.

## Confirmed findings

1. Issue `#106` is open and still applicable to `main`.
2. The backend can emit safe SSE `error` events from `/api/chat/stream`.
3. Backend tests already verify that raw provider errors are not exposed in SSE
   `error` payloads.
4. The frontend stream parser currently handles `token`, `sources`, and `done`
   events, but ignores `error` events.
5. The frontend stream parser resolves successfully when the HTTP body reaches
   EOF, even if no `done` event was received.
6. The chat controller only enters its stream failure path when
   `streamChatResponse()` throws. A silent EOF without `done` can therefore
   leave an empty or partial assistant message without a clear failure state.
7. Current E2E coverage includes happy-path streaming and HTTP failure before
   streaming starts, but not SSE `error` events or partial streams without
   `done`.

## Target behaviour

1. A successful chat stream must end with a valid `done` event.
2. SSE `error` is a terminal failure event and must be visible to the user.
3. EOF before `done` is an incomplete stream, not a successful answer.
4. If streaming fails before any answer token is received, the frontend may use
   the existing JSON fallback and preserve structured metadata from that
   fallback response.
5. If streaming fails after one or more answer tokens are visible, do not replay
   through JSON fallback. Keep the partial text visible and show an explicit
   incomplete-stream notice.
6. Do not apply sources, confidence, retrieval status, or handoff metadata unless
   the stream completed with `done`.
7. User-initiated abort/reset/unmount should remain silent and must not show an
   error notice.

## Delivery plan: one PR, three commits

The work is planned as one pull request with three logical commits.

After every step:

- update the status table and verification log in this file;
- run the smallest relevant check for that step;
- stop and report the result;
- provide a Conventional Commits message;
- continue to the next local commit only after the user confirms.

| Step | Commit scope | Required result |
| --- | --- | --- |
| 1 | `test(chat-ui): cover failed and incomplete chat streams` | Playwright regressions demonstrate the current SSE `error` and missing-`done` failures |
| 2 | `fix(chat-ui): handle chat stream terminal failures` | Stream parser and controller distinguish completed, failed, incomplete, fallback, and abort states |
| 3 | `docs(chat): document stream terminal semantics` | API/chat docs define `done` as the only successful terminal event and `error` as terminal failure |

## Execution plan

### Step 1 - Regression tests

- Add E2E coverage for backend SSE `event: error` before any token.
- Add E2E coverage for a stream that sends a token but closes before `done`.
- Add E2E coverage for a stream that closes before any token and before `done`.
- Preserve existing happy-path and HTTP 503 JSON fallback coverage.
- Expected interim result: new tests fail on the current implementation.

### Step 2 - Frontend stream handling

- Add typed stream terminal errors/results in `frontend/lib/chat-api.ts`.
- Track whether the stream received a valid `done` event.
- Parse SSE `error` payloads and throw a safe user-facing stream error.
- Treat EOF without `done` as an incomplete stream.
- Validate `Content-Type` starts with `text/event-stream`.
- Keep JSON fallback only for failures before the first answer token.
- For failures after partial text, flush visible text and show the incomplete
  stream notice.
- For failures before any usable text and failed JSON fallback, replace the empty
  assistant message with the generic assistant error message.

### Step 3 - Documentation

- Update `docs/api-contract.md` with explicit terminal-event semantics.
- Update `docs/rag-and-ai-safety.md` only if the frontend fallback paragraph
  needs the same clarification.
- Keep docs focused on behaviour and avoid changing architecture/deployment
  guidance unless the implementation proves it necessary.

## Status table

Status values: `COMPLETE`, `IN_PROGRESS`, `PENDING`, `BLOCKED`.

Current stage: Step 1 regression tests are complete and intentionally fail on
the current implementation. Waiting for the user's local commit confirmation
before Step 2 implementation.

| ID | Work item | Status | Evidence / current result | Next gate |
| --- | --- | --- | --- | --- |
| 0.1 | Create local work branch | COMPLETE | `codex/fix-chat-stream-terminal-errors` created from `main` | Keep work local until push approval |
| 0.2 | Record scoped work plan | COMPLETE | `SESSION_NOTES.md` now describes issue `#106`, target behaviour, and three-commit delivery plan | Begin Step 1 regression tests |
| 1.1 | Add failing frontend stream-error regressions | COMPLETE | New Playwright spec covers SSE `error`, partial EOF without `done`, and empty EOF without `done`; focused run fails on current implementation as expected | Commit Step 1 before implementation |
| 2.1 | Implement stream terminal-state handling | PENDING | Not started | Run focused Playwright tests until passing |
| 2.2 | Run frontend quality gate | PENDING | Not started | Run `task frontend:check` |
| 3.1 | Document stream terminal semantics | PENDING | Not started | Run docs-adjacent checks if required |
| 3.2 | Final verification and report | PENDING | Not started | Run final scoped checks and prepare commit summary |

## Verification log

| Date | Check | Result |
| --- | --- | --- |
| 2026-08-28 | Git worktree before branch creation | Clean; `main` matched `origin/main` |
| 2026-08-28 | Create branch | `codex/fix-chat-stream-terminal-errors` created |
| 2026-08-28 | Issue and code review | Issue `#106` remains open; frontend ignores SSE `error` and treats EOF without `done` as success |
| 2026-08-28 | Step 1 focused Playwright regression run | `npx playwright test chat-stream-errors.spec.ts --project=chromium --workers=1 --reporter=line` produced the expected failures: SSE `error` leaves `Understanding your question.`, partial EOF has no incomplete-stream notice, and empty EOF leaves `Understanding your question.`; command was interrupted after detailed failure reports because Playwright did not return a final summary promptly |

Update the status table and verification log as work progresses. Do not mark a
work item complete until its implementation and stated verification gate both
pass.
