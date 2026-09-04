# Repeat handoff after close work

Last updated: 2026-09-03

Branch: `codex/allow-new-handoff-after-close`

GitHub issue: `#103` - `P2: Allow a new handoff request after a handoff is closed`

## Work boundary

This branch is for fixing the chat UI lifecycle after a human handoff is closed.
Keep changes scoped to:

- frontend handoff lifecycle state in `use-chat-controller`;
- focused Playwright coverage for requesting a new handoff after a closed one;
- documentation only if the implemented behaviour changes or clarifies an
  existing API/UI contract.

Do not change backend escalation APIs, Telegram webhook behaviour, RAG
retrieval, deployment settings, unrelated chat UI flows, or issue `#107`
owner-message context handling. Do not push the branch or open a pull request
without explicit approval.

## Confirmed findings

1. Issue `#103` is open and still applicable to `main`.
2. The chat UI sets `escalationSent` to `true` after a successful handoff
   request.
3. The handoff prompt is hidden while `escalationSent` is `true`.
4. `escalationSent` is reset by full chat reset, but not by manual handoff close
   or SSE `closed` events.
5. The UI copy says visitors can request a new connection after the handoff is
   closed.
6. Existing Playwright coverage checks that messages after manual close return
   to AI chat, but does not check that a later backend handoff suggestion can
   show a new prompt.

## Target behaviour

1. During an active handoff, duplicate handoff prompts remain blocked.
2. When a handoff reaches a terminal `closed` state, the one-shot
   `escalationSent` guard is reset.
3. This applies to manual close and backend/SSE `closed` events.
4. A later AI response with `handoff_suggested: true` can show a fresh handoff
   prompt after the previous handoff is closed.
5. Dismissing a specific handoff prompt still suppresses only that prompt.
6. Normal AI chat, active handoff messaging, and close flows continue to work.

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
| 1 | `test(chat-ui): cover repeat handoff after close` | Playwright regression demonstrates that a second handoff prompt is currently blocked after close |
| 2 | `fix(chat-ui): allow new handoff after close` | Manual close and SSE close reset the handoff prompt guard without allowing duplicate prompts during active handoff |

## Execution plan

### Step 1 - Regression test

- Extend `frontend/e2e/chat-handoff.spec.ts` with a focused scenario:
  first AI response suggests handoff, visitor connects, handoff closes, later AI
  response suggests handoff again.
- Assert the second chat request goes to `/api/chat/stream`, not the escalation
  message endpoint.
- Assert the second handoff prompt becomes visible after the closed state.
- Run the focused Playwright spec and confirm the new scenario fails on current
  `main` behaviour.

### Step 2 - Frontend lifecycle fix

- Reset `escalationSent` when `handleEscalationStreamClosed` moves the handoff
  to `closed`.
- Reset `escalationSent` after a successful manual `closeHandoff`.
- Keep `escalationSent` set during `waiting_for_alex`, `connected`, and `error`
  states so active handoff sessions do not show duplicate prompts.
- Re-run the focused handoff spec.
- Run the smallest relevant frontend quality checks; use `task frontend:check`
  before final report unless there is a clear environment blocker.

### Step 3 - Documentation check

- Review `docs/api-contract.md`, `docs/architecture.md`, and handoff setup docs
  only around closed-handoff behaviour.
- Update docs only if the implementation reveals a mismatch or missing contract
  detail.
- Run `git diff --check`.

## Status table

Status values: `COMPLETE`, `IN_PROGRESS`, `PENDING`, `BLOCKED`.

Current stage: Step 2 implementation, frontend verification, and documentation
check are complete. Waiting for the user's local commit before any push or pull
request work.

| ID | Work item | Status | Evidence / current result | Next gate |
| --- | --- | --- | --- | --- |
| 0.1 | Create local work branch | COMPLETE | `codex/allow-new-handoff-after-close` created from `main` | Keep work local until push approval |
| 0.2 | Replace session notes with scoped plan | COMPLETE | `SESSION_NOTES.md` now contains only issue `#103` plan and boundaries | Begin Step 1 regression test |
| 1.1 | Add repeat-handoff regression coverage | COMPLETE | `frontend/e2e/chat-handoff.spec.ts` now covers a second handoff prompt after manual close and after SSE `closed`; both scenarios reach the second AI response but fail because the new handoff prompt is not shown | Commit Step 1 before implementation |
| 2.1 | Implement closed-handoff lifecycle reset | COMPLETE | `use-chat-controller` now resets `escalationSent` when a handoff closes through manual close or SSE `closed`, while leaving the guard active during waiting/connected/error states | Run frontend verification |
| 2.2 | Run frontend verification | COMPLETE | Focused repeat-handoff tests passed 2/2, full handoff spec passed 11/11, and `task frontend:check` passed with 80/80 built E2E tests | Check docs for lifecycle contract mismatch |
| 3.1 | Check docs for lifecycle contract mismatch | COMPLETE | Existing API, architecture, and handoff setup docs already state that closing a handoff returns new messages to normal AI chat flow; no docs update needed | Run final diff hygiene |
| 3.2 | Final diff hygiene and report | COMPLETE | `git diff --check` passed for the final Step 2 diff; Git reported only expected LF-to-CRLF working-copy warnings | Commit Step 2 before any push or PR |

## Verification log

| Date | Check | Result |
| --- | --- | --- |
| 2026-09-02 | Git worktree before branch creation | Clean `main`; local `main` matched `origin/main` |
| 2026-09-02 | Create branch | `codex/allow-new-handoff-after-close` created |
| 2026-09-02 | Step 1 focused Playwright regression run | `PLAYWRIGHT_USE_DEV_SERVER=true npx playwright test chat-handoff.spec.ts -g "new handoff prompt" --project=chromium --workers=1 --reporter=line` showed the expected failures in both new tests: the second AI response appeared, but `Would you like to connect with Alex?` was not rendered after manual close or SSE `closed`; the hanging Playwright process was interrupted after failure details were printed |
| 2026-09-03 | Step 2 focused Playwright verification | `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3010 npx playwright test chat-handoff.spec.ts -g "new handoff prompt" --project=chromium --workers=1 --reporter=line` passed 2/2 against a manually started dev server |
| 2026-09-03 | Step 2 full handoff Playwright verification | `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3010 npx playwright test chat-handoff.spec.ts --project=chromium --workers=1 --reporter=line` passed 11/11 against a manually started dev server |
| 2026-09-03 | Step 2 frontend quality gate | `task frontend:check` passed: install, lint, typecheck, resume parser, production build, Playwright install, and 80/80 built E2E tests; npm audit still reports existing dependency findings: one low and one high |
| 2026-09-03 | Step 3 docs review | `docs/api-contract.md`, `docs/architecture.md`, and `docs/telegram-handoff-setup.md` already describe closed handoff returning new messages to normal AI chat flow; no documentation changes required |
| 2026-09-03 | Step 2 final diff whitespace check | `git diff --check` passed for `SESSION_NOTES.md` and `frontend/hooks/use-chat-controller.ts`; Git reported only expected LF-to-CRLF working-copy warnings |

Update the status table and verification log as work progresses. Do not mark a
work item complete until its implementation and stated verification gate both
pass.
