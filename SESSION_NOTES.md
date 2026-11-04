# Architecture refactor — active execution ledger

Updated: 2026-11-04. This is a human-maintained handoff document, not a CI
contract. The Fleet API work is in branch `refactor/fleet-api-delivery-boundaries`.
Last GitHub HEAD checked: `4526334dcf2dfd01f4c20b3a623beb46d5070286`.

## Operating rules

- One concern per reviewable PR; preserve all Fleet public routes and the
  website Chat/RAG/SSE behavior.
- Protect the Fleet seed (SHA-256:
  `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`),
  `VOR_DEMO_DB_PATH` and all existing runtime data.
- Tests must use temporary SQLite copies; never reset production data.
- Do not check this document's contents, title, hash or existence in CI,
  installers or tests. The file is documentation, not a build gate.
- Record test claims with their source: user-reported local passes are not
  evidence of GitHub Actions or production deployment verification.

## Completed milestones

| Work | Status | Evidence |
| --- | --- | --- |
| Fleet persistence lifecycle / migrations | Merged | PR #223, squash merge `c020c813d452`, 2026-11-04 |
| 05A — Shared session and Origin guards | Committed | `a06608cd`; `api/dependencies.py`, auth regression tests |
| 05B — Email policy and Resend service | Committed | `328a4487`; `services/message_delivery.py`, provider/HTTP regression tests |
| 05C — Keyed live-email deduplication | Committed | `4526334d`; SQLite request journal, API and browser request IDs, retry/failure tests; local tests reported green |
| 05D — Documentation and final PR review | In progress | Docs sync, full diff review, final local `task ci`, GitHub PR checks pending |

## Current constraints and risks

- Successful keyed requests replay their saved API response without a second
  provider call, event or quota reservation. Concurrent and uncertain keyed
  requests fail closed pending investigation.
- Provider acceptance, SQLite event creation and journal completion cannot be
  committed atomically. Unknown outcomes require manual reconciliation.
- Resend retains idempotency keys for 24 hours. Our local journal retains
  keyed request history until removed administratively.
- Legacy unkeyed API callers can still create repeated emails. The browser
  currently retains a request key within a mounted component, not across a
  full page reload.
- There is no new infrastructure and no independent Fleet deployment.

## Next task

1. Inspect the entire `main...refactor/fleet-api-delivery-boundaries` diff.
2. Run targeted Fleet tests and full `task ci`; review security/privacy and
   verify the approved seed is unchanged.
3. Push final documentation commit and open a single Fleet API PR into `main`.
4. Wait for GitHub checks, then squash merge and verify deployment smoke.
5. Next separate concern: site repository-to-domain dependency inversion and
   cross-layer import guards, not another feature in this PR.
