# Architecture refactor — active execution ledger

Updated: 2026-11-05. This is a human handoff document, **not** an input to
CI, installers, guards or hash validation.

## Verified merged foundation

- PR #223 merged Fleet SQLite lifecycle and legacy migrations into `main`.
  Squash commit: `c020c813d45231442d1cebba20367fd4c4d49443`.
- PR #224 merged Fleet HTTP authentication, email orchestration and keyed
  delivery deduplication into `main` on 2026-11-05.
  Squash commit: `dbc270ce32dd846d124792c3ad53e18092998e1c`.
- GitHub Actions on the new `main` commit were checked after merge:
  backend, project, docker, RAG and CodeQL passed; frontend was still
  running at the last inspection. Do not assume full green or production
  verification without checking their final results.
- No new Fleet infrastructure is deployed. Approved Fleet SQLite seed
  SHA-256 remains
  `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`.

## Current branch / Step 06

Branch: `refactor/backend-domain-dependencies`.
Baseline `main` commit checked: `dbc270ce32dd846d124792c3ad53e18092998e1c`.

Goal: correct the site backend repository-to-service dependency direction
without modifying escalation behaviour, wire formats, endpoints or infrastructure.

- Move pure session records, state names and transition functions from
  `app.services.escalation_session_state` into `app.domain.escalation_session`.
- Keep the old services import module as a re-export compatibility facade.
- Point repository protocol and Upstash adapter directly at the domain model.
- Point application services directly to the domain state implementation.
- Add temporary-free, network-free tests covering import identity, record JSON,
  TTL, transitions, Upstash command shape and repository import direction.
- Treat Redis `GET` -> state transition -> `SET` concurrency as a separate
  **unverified** risk; do not redesign or change Redis writes in Step 06.

## Operating safeguards

- Keep existing `handoff_id`, state strings, message roles, JSON payload shape
  and Redis TTL semantics. Legacy public function names are compatibility API.
- Do not change Telegram, SSE, chat, Fleet, deployment or user-visible copy.
- No production Redis access is required for regression tests.
- Keep `SESSION_NOTES.md` out of CI and installer preflight; its contents,
  title, hash and existence must never gate code changes.
- Maintain small PRs and distinguish user-reported local `task ci` success,
  GitHub Actions success and manual production smoke.

## Next actions

1. Apply Step 06 on the new branch; review `git diff` and run focused tests.
2. Run the complete `task ci`, commit and push if green.
3. Open one Step 06 PR; wait for GitHub CI, then squash merge.
4. Start Step 07 separately: AST-based import-graph CI guard with positive and
   negative fixture tests; avoid a large dependency injection framework.
5. Later, assess Chat SSE and the large frontend chat controller in separate PRs.


## Step 07 — Python import-boundary CI guard

Status: implementation staged on `test/backend-import-boundaries` after
verified PR #225 squash merge `1827f8d35aca307492246a625cb58de628588461`.
Step 06 is merged; its earlier planned action list above is historical.

- Scope: AST-based direction checks for `app.domain`, `app.repositories`,
  `fleet_hub.services` and Fleet HTTP sibling routers.
- CI entry: `task backend:imports`, invoked from `backend:check` and therefore
  by both local `task ci` and GitHub Actions backend job.
- Known pre-existing API edge: `fleet_hub.api.vor` →
  `fleet_hub.api.vor_checklist`; grandfathered exactly once. Remove in a
  separate behaviour-preserving change; do not expand the exception.
- Add positive/negative fixture tests. No runtime module, HTTP route,
  Redis, SQLite, Docker, or frontend source changes.
- Independent fixture testing passed when packaging; full local `task ci`,
  GitHub PR checks and post-merge verification are not yet confirmed.
- No script, test, CI check or preflight reads this ledger as a gate.

Next: install, inspect diff, run targeted tests + full CI, commit and push,
open a focused PR, then squash merge after GitHub checks pass. Next scope
should be Chat SSE only after confirming the updated architecture guard.

## Step 08 — Chat stream transport boundary

Status: working branch `refactor/chat-sse-boundaries`; base `main` merge of
PR #226, `99936c50afbd87aff152ffbaea50b6845c35ed77`.

- Step 07 architecture import guards were merged as PR #226 on 2026-11-05.
- Chat application service and metrics now use `app.domain.chat_stream.ChatStreamEvent`
  rather than SSE transport-specific schemas.
- `app.api.chat` translates logical events to existing SSE bytes using `sse_event`.
- Golden-wire, safe-error, disconnect and dependency-boundary tests cover the
  move. Existing API/SSE/RAG/Telegram behavior must remain unchanged.
- No Redis, Fleet seed, deployment or environment configuration changes.
- Local full `task ci`, GitHub PR checks and deployment smoke are pending;
  do not infer their success from isolated patch tests.

Next: run focused backend tests and `task ci`; push this focused PR only when
all checks pass. After squash merge, independently examine Chat cancellation,
backpressure and the frontend chat controller in subsequent scoped work.


## Step 09A — Chat response flow extraction (2026-11-06)

- Step 08 was squash-merged as PR #227 at `19dae9b88832ef7c1f0f923b641097a212b14c01`.
- Branch: `refactor/chat-response-flow`. Only SSE/JSON assistant response
  orchestration moves from `use-chat-controller.ts` to
  `frontend/lib/chat-response-flow.ts`.
- React state, handoff, rendered transcript, abort ownership, focus, warmup,
  API request payloads and public UI stay in the controller unchanged.
- Six deterministic Playwright-runner tests cover done/sources, errors,
  partial tokens, JSON fallback and abort. Existing browser E2E remains required.
- Known pre-existing reset/cancellation race is *not* redesigned here; audit
  callback ownership in a separate tested step before changing lifecycle logic.
- No production secrets or Fleet/Redis/RAG changes.
- Run focused tests, `task ci`, GitHub PR CI and then squash merge.
- This ledger is never an installer/test/CI preflight input.


## Step 09B — stale async Chat request guards (2026-11-06)

- Step 09A was squash-merged as PR #228 at `7f7c80e2739e46bf1ee08b1c3496f1d31f63dce4`.
- Branch: `fix/chat-request-lifecycle`. An assistant request lease owns
  response patches, notices, rendering updates, thinking-state cleanup and focus.
- Reset/unmount invalidates both request leases and handoff session generations.
  Late handoff connect/message/close outcomes are ignored by the cleared UI.
- A closed/replaced EventSource may not deliver a queued callback into the
  current chat. Keep native EventSource and existing Last-Event-ID semantics.
- No backend, wire payload, Redis, Telegram or Fleet changes. A handoff POST
  already accepted by the server cannot be undone by client-side Reset.
- New pure lease tests and browser race regressions require complete `task ci`
  and GitHub CI. Never treat this ledger as a test/preflight gate.

## Step 09B lint correction

- Initialize the request lifecycle via the lazy `useState` initializer; do not read or write React refs during render.
- No API, state-machine, handoff, transport, or payload changes. Run `task frontend:lint`, `task frontend:typecheck`, and full `task ci` before committing.
