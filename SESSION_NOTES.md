# Telegram handoff duplicate close-message work

Last updated: 2026-09-08

Branch: `codex/avoid-duplicate-telegram-close-message`

GitHub issue: `#104` - `P2: Avoid duplicate close messages when handoff is closed from Telegram`

## Work boundary

This branch is for preventing duplicate visitor-facing close messages when the
Owner closes a handoff from Telegram. Keep changes scoped to:

- Telegram callback close behaviour in the backend;
- escalation session stream semantics around stored messages and `closed`
  events;
- focused backend regression coverage for callback close and SSE close output;
- documentation only if the implemented behaviour changes or clarifies an
  existing handoff contract.

Do not change frontend chat lifecycle, RAG retrieval, chat completion logic,
deployment settings, Telegram webhook authentication, or issue `#107`
owner-message AI context handling. Do not push the branch or open a pull
request without explicit approval.

## Confirmed findings

1. Issue `#104` is open and still applicable to `main`.
2. Telegram callback close currently calls the session store with a
   visitor-facing `close_message`.
3. The session close transition stores that `close_message` as an `alex`
   message.
4. The escalation stream emits stored `alex` messages before emitting the SSE
   `closed` event.
5. The frontend renders `alex` messages and also appends its own close copy when
   it receives the SSE `closed` event.
6. Therefore callback close can produce two visitor-facing close messages: a
   stored Owner close message and the frontend-generated SSE close message.

## Target behaviour

1. SSE `closed` is the single source of visitor-facing close copy.
2. Closing from a Telegram callback closes the session without appending a
   stored `alex` close message.
3. Telegram operator confirmation remains unchanged.
4. Manual `/close` command behaviour remains consistent with callback close.
5. Expiry still emits the correct `session_expired` close event.
6. Existing quick replies and manual owner replies continue to be delivered as
   visitor-visible `alex` messages.

## Delivery plan: one PR, two commits

The work is planned as one pull request with two logical commits.

After every step:

- update the status table and verification log in this file;
- run the smallest relevant check for that step;
- stop and report the result;
- provide a Conventional Commits message with an emoji and concise description;
- continue to the next local commit only after the user confirms.

| Step | Commit scope | Required result |
| --- | --- | --- |
| 1 | `test(handoff): cover Telegram close without visitor message` | Backend regression demonstrates that callback close currently passes a visitor-facing close message to the session store |
| 2 | `fix(handoff): avoid duplicate Telegram close messages` | Callback close closes the session without appending an `alex` close message, while operator confirmation and stream `closed` behaviour remain intact |

## Execution plan

### Step 1 - Regression test

- Update focused Telegram webhook close coverage so callback close expects the
  session store to receive no visitor-facing `close_message`.
- Preserve assertions that the callback is acknowledged and the operator gets a
  Telegram confirmation.
- Run the focused backend test and confirm it fails on current `main`
  behaviour.

### Step 2 - Backend fix

- Change Telegram callback close to call session close without `close_message`.
- Remove obsolete visitor-facing close-copy plumbing if it becomes unused.
- Keep quick reply and manual owner reply storage unchanged.
- Re-run focused Telegram webhook close tests.
- Run adjacent backend tests for callback, stream, and session state behaviour.
- Run `task backend:check` before final report unless there is a clear
  environment blocker.

### Step 3 - Documentation check

- Review `docs/api-contract.md`, `docs/architecture.md`, and
  `docs/telegram-handoff-setup.md` around Telegram close and SSE `closed`.
- Update docs only if they still imply Telegram callback close should send a
  separate visitor-facing close message.
- Run `git diff --check`.

## Status table

Status values: `COMPLETE`, `IN_PROGRESS`, `PENDING`, `BLOCKED`.

Current stage: Step 1 regression coverage is complete. Waiting for the user's
local commit before Step 2 implementation.

| ID | Work item | Status | Evidence / current result | Next gate |
| --- | --- | --- | --- | --- |
| 0.1 | Create local work branch | COMPLETE | `codex/avoid-duplicate-telegram-close-message` created from clean `main` | Keep work local until push approval |
| 0.2 | Replace session notes with scoped plan | COMPLETE | `SESSION_NOTES.md` now contains only issue `#104` plan and boundaries | Begin Step 1 regression test |
| 1.1 | Add callback-close regression coverage | COMPLETE | `backend/tests/test_telegram_webhook_close.py` now expects Telegram callback close to close the session without a visitor-facing `close_message`; focused test fails on current behaviour because the callback still passes close copy into the session store | Commit Step 1 before implementation |
| 2.1 | Implement Telegram callback close fix | PENDING | Not started | Focused backend tests should pass |
| 2.2 | Run backend verification | PENDING | Not started | Adjacent tests and `task backend:check` or documented blocker |
| 3.1 | Check docs for close-message contract mismatch | PENDING | Not started | Update docs only if needed |
| 3.2 | Final diff hygiene and report | PENDING | Not started | `git diff --check` and commit message |

## Verification log

| Date | Check | Result |
| --- | --- | --- |
| 2026-09-08 | Git worktree before branch creation | Clean `main`; local `main` matched `origin/main` |
| 2026-09-08 | Create branch | `codex/avoid-duplicate-telegram-close-message` created |
| 2026-09-08 | Step 1 focused backend regression run | `UV_CACHE_DIR=.tmp/uv-cache UV_PROJECT_ENVIRONMENT=.tmp/backend-venv uv run --extra dev python -m pytest tests/test_telegram_webhook_close.py -q` failed as expected: 1 failed, 2 passed; callback close still passed `This conversation has been closed because there was no response for a while...` as `close_message` instead of `None` |
| 2026-09-08 | Step 1 diff whitespace check | `git diff --check` passed; Git reported only expected LF-to-CRLF working-copy warnings |

Update the status table and verification log as work progresses. Do not mark a
work item complete until its implementation and stated verification gate both
pass.
