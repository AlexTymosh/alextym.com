# SESSION_NOTES.md — Architecture refactor execution ledger

Snapshot: `main@88b24f5d24a7ee69aed0ec6db460af10afa3218c` (2026-11-02). Audit: `docs/architecture/boundaries-audit.md` (copy the supplied audit into this path before implementing). The documentation bootstrap (00) is `in_progress` after applying this archive, but MUST NOT be committed alone. It is bundled into the first code refactoring PR. Remaining steps are planned, not executed.

## Operating contract

- Read `AGENTS.md`, this file, and the audit; read `docs/architecture.md`, `docs/architecture/portfolio.md` and other documentation **only for the active task**. Verify `git rev-parse HEAD` and `git status --short --branch` before editing; re-audit changed targets if `main` has advanced.
- Execute **one architectural concern / one reviewable PR** at a time (the first PR bundles 00 + 01 + 02). Write characterization tests before moving risky code. Prefer behaviour-preserving extraction, not feature or UI changes.
- Protect runtime Fleet SQLite files, `VOR_DEMO_DB_PATH` and seed SHA-256 `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`. Use isolated temporary databases for tests; never reset live data. Preserve 56 Fleet route methods, auth/cookies/Origin, email policy, all site/Chat/RAG/SSE contracts and single Vercel + Render hosts.
- Dependency rule: host → Fleet public entry; API → service/use case → persistence + pure rules. No `repositories → services`, Fleet internals → host business modules, service → FastAPI Request/Response, or shared router dependency imported from sibling router. Enforce only after characterizing existing compatibility imports.
- On every step: inspect diff, run targeted tests plus `task ci`, record factual results and commit/PR reference in row. Status: `todo | in_progress | blocked | done`. Mark `done` **only** after tests pass and code is committed; record CI/merge separately. If unable to test, set `blocked` with reason, not `done`.
- No new services, frameworks, infrastructure, route-group rewrite, unnecessary DTO layers or changes outside scope. Preserve PR/commit style and update this ledger in every refactor PR.

## Execution table

| ID | Focus | Status | Required change / target | Exit gate | Evidence / blocker |
|---|---|---|---|---|---|
| 00 | Audit bootstrap (not a standalone PR) | in_progress | Add audit and execution ledger on `refactor/architecture-boundaries-2026-11-02`, leave docs uncommitted until actual Fleet DB tests and refactor are present | Review audit diff; combine with 01 + 02 in one refactor PR | Bootstrap only; NO docs-only commit or PR. |
| 01 | Fleet DB tests (same PR as 02) | in_progress | `portfolio/fleet_hub/tests/`: fresh/legacy temp SQLite, repeated bootstrap, concurrent opens, rollback, seed/DB safety/API baseline | Focused pytest + `task ci` | — |
| 02 | Fleet persistence (first refactor PR) | in_progress | `fleet_hub/services/vor_store.py`, `vor_data.py`, `vor_operations.py`: extract shared connection/explicit schema initialization; preserve migrations and data | Tests 01 + `task ci`; no read-path DDL except explicitly approved initialization | — |
| 03 | Fleet HTTP/email | todo | `fleet_hub/api/vor*.py`: move shared auth/origin to API dependency; move mail policy/provider orchestration out of `create_message` | Auth/mail failure and quota tests + `task ci`; stable cookie and statuses | — |
| 04 | Dependency inversion | todo | `app/repositories/upstash_escalation_session_store.py` → neutral `app/domain/escalation_session.py`; add backend AST/Fleet frontend boundary guard tests | No repository→service or sibling-router shared-dependency imports + `task ci` | — |
| 05 | Chat stream | todo | `app/services/chat.py`, `app/api/chat.py`, `app/api/sse.py`: isolate SSE mapping, retain safety buffering and fallback | JSON/SSE golden tests + `task ci` | — |
| 06 | Chat UI controller | todo | `frontend/hooks/use-chat-controller.ts`: characterize abort/reset/handoff then extract pure state/action seams; no UI restyle | Frontend lint/typecheck/E2E + `task ci` | — |
| 07 | Doc synchronization | todo | Update `AGENTS.md`, `portfolio/fleet_hub/README.md`, `docs/architecture/portfolio.md` for merged PR #216 and current topology; move old notes to archive if needed | Link and instructions review + `task ci` if code changed | — |
| 08 | Final verification | todo | Audit residual A-07 to A-09 only if justified; ensure relevant invariant/guard tests and no undocumented boundary violations | Full `task ci`, PR CI, manual production smoke as applicable | — |

## Current working checkpoint (uncommitted, 2026-11-03)

- Branch: `refactor/architecture-boundaries-2026-11-02`, HEAD `88b24f5d24a7`.
- Step 01: low-level SQLite connection lifecycle extraction and four temporary-DB tests installed; developer-confirmed `task ci` 8/8 PASS before this step-02 extraction.
- Repository hygiene: obsolete PR-title assertion repaired; CI 8/8 PASS after repair.
- Step 02A (this patch): move existing v1.0/v1.1/v1.2 migration implementations into `fleet_hub.persistence.migrations`; preserve `vor_store.migrate_v1*` compatibility facades and call order. Does **not** move schema initialization off request paths.
- Next: run targeted tests and full `task ci`; record results. Keep steps 00-02 `in_progress` until code is committed. No push/PR yet.
- Later Fleet SQLite work: characterize v2/operations DDL, then centralize bounded schema bootstrap and preserve existing runtime DBs.
- Frontend lint currently reports seven existing warnings; fix in a separate frontend-focused stage, without suppression.

## Commit and handoff protocol

1. Start on `refactor/architecture-boundaries-2026-11-02`. This bootstrap is documentation only and does NOT justify a commit or PR. Implement Fleet DB characterization tests (01) and real persistence refactor (02) on this branch, then commit code + documents together in one refactor PR. After that merge, use fresh concern-specific refactor branches for other steps. Do not pre-mark downstream rows complete.
2. After implementing a row, append in `Evidence / blocker`: commit SHA, tests with results, PR number and whether merged; update its status. If blocked, state exact failure and leave later steps untouched.
3. Before handoff print: current branch and HEAD, completed ID, changed files, tests run, unresolved risks, next single ID. Use `Owner` in reusable descriptions; do not insert identifying personal names.

**Stop:** CI failure, unexpected route/response/SSE/auth/seed change, runtime DB touch, unknown state of an in-flight PR, or broad scope drift. Do not solve failures by deleting tests or weakening contracts.
