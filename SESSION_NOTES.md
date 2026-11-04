# Architecture refactor — active execution ledger

Updated: 2026-11-04. First PR branch:
`refactor/architecture-boundaries-2026-11-02`.
Last GitHub HEAD independently checked before this documentation patch:
`4da72d53b31445bbd73a852ba97bf1e0aaa7e1f4`.
This document reports the branch state, not a merged PR.

## Operating rules

- Keep changes scoped: one concern per reviewable PR, with characterization
  tests before risky refactors. Avoid new services or infrastructure.
- Preserve public routes, HTTP/auth/Origin and site Chat/RAG/SSE contracts.
- Protect the immutable Fleet seed (SHA-256:
  `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`),
  `VOR_DEMO_DB_PATH`, and all existing runtime SQLite data.
- Use temporary SQLite databases for automated tests. Never migrate or reset a
  production database in CI.
- No installer, CI script or test may check the content, title, hash or
  existence of this file. This is a human handoff document, not a build gate.
- Record observed test results honestly. Do not treat a local green run as
  evidence of GitHub PR checks or production verification.

## Milestones

| Work | State | Evidence / next action |
| --- | --- | --- |
| Architecture audit and initial ledger | Committed | First branch commit `e6ea977d`; `docs/architecture/boundaries-audit.md` is a historical baseline audit. |
| Shared SQLite lifecycle and v1 migration extraction | Committed | `e6ea977d`; compatible wrappers and temporary-DB regressions. |
| Warm v1 schema readiness | Committed | `f4243c05`; extra first-seed regression. |
| v2/operations schema readiness | Committed | `a0bc85b9`; no repeated DDL for prepared schema. |
| Concurrent bootstrap and atomic seed publication | Committed | `4b49879c`; cross-process tests. |
| FastAPI lifespan preparation | Committed | `94a17c1c`; optional Fleet startup remains isolated from host health. |
| Lock-free warm v1 connection path | Committed | `b65a7e51`; readiness recheck under lock on cold path. |
| Rollback and retry of interrupted v1 migration | Committed | `4da72d53`; user reported green tests; full PR CI still pending. |
| Documentation synchronization | In progress | Align `AGENTS.md`, Fleet README, portfolio architecture, and this ledger; review and commit together. |
| First architecture PR | Pending | Final diff review, `task ci`, GitHub checks; create PR into `main` then squash merge. |
| Fleet API auth/email isolation | Todo | New branch after first PR. |
| Repository/domain dependency inversion | Todo | New branch after Fleet API. |
| Chat SSE and UI architecture | Todo | Subsequent, focused changes; no feature redesign. |
| Frontend ESLint 10 update | Todo | Separate dependency-maintenance branch after architecture work. |

## Current checkpoint

- First PR is NOT opened or merged based on the last inspected GitHub state.
- The source code at HEAD has seven commits on this branch beyond `main`;
  after the documentation commit, verify the new HEAD and compare again.
- SQLite safety caveat: rollback is version-local, not atomic across every
  version; no production DB or full PR deployment smoke has been exercised by
  the assistant. Bootstrap uses a sidecar lock file adjacent to runtime SQLite.
- This documentation step does not alter source, API, seed, or migrations.

Next: apply this documentation update, inspect the diff, run `task ci`, commit
and push to the same branch. Then review the resulting PR diff and GitHub CI.
