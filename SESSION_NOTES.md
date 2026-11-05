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
