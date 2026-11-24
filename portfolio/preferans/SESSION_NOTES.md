# Preferans — Session Notes

**Project ID:** `preferans`
**Folder:** `portfolio/preferans/`
**Site route:** `/portfolio/preferans`
**Version:** 2.0 / 2026-11-24 (modernization handoff)
**Inspected main:** `93611d3ea7c67a5762888c6ed17bd146406d7d4c`
**Status:** PLANNING ONLY. Owner authorization to implement PR 10 is pending.

## 1. Next action — STOP before implementation

- Owner creates `feat/preferans-realtime` from updated `main`, saves the three
  planning documents, optionally commits them, and explicitly authorizes PR 10.
- No product source, tests, assets, deployment, IAM, billing, or database changes
  are authorized by this documentation handoff. Do not begin PR 10 merely because
  this file exists or because the planning commit is on its branch.
- On explicit authorization, read the current branch/status/diff, refreshed main,
  root `AGENTS.md`, the relevant host contracts, and PR 10 in the new plan.
  Start with slice 10.A (baseline, ADR, gap inventory). Do not begin PR 11–14.

## 2. Authoritative documents (read selectively)

1. [Modernization specification](docs/MODERNIZATION_TECHNICAL_SPECIFICATION.ru.md)
   — PREF-MOD-TRS-001 v1.0, approved UX-01–14 and NFRs, transport/UX/media design,
   acceptance matrix and explicit implementation defaults.
2. [Modernization development plan](docs/MODERNIZATION_DEVELOPMENT_PLAN.ru.md)
   — PREF-MOD-PLAN-001 v1.0, PR 10–14, slices, scope and completion gates.
3. [Original full specification](docs/FULL_TECHNICAL_SPECIFICATION.ru.md),
   [House rules](docs/HOUSE_RULES.ru.md), [confirmed decisions](docs/HOUSE_RULES_DECISIONS.ru.md),
   [scoring](docs/SCORING_ENGINE.ru.md). Keep existing historical rules, formulas,
   validated golden tests and immutable results. Modernization changes only the
   explicitly identified UX/transport requirements. No new house rules by inference.
4. Root `AGENTS.md`, `docs/architecture.md`, `docs/architecture/portfolio.md`,
   `docs/api-contract.md`, `docs/security-privacy.md`, `docs/deployment.md` when relevant.
   The root `SESSION_NOTES.md` belongs to the website; leave it unchanged here.
5. Historical release evidence: [PR 9 release candidate](docs/PR09_RELEASE_CANDIDATE.ru.md),
   [PR 9 UAT](docs/PR09_UAT.ru.md), [HTTP 503 investigation](docs/HTTP_503_FIRESTORE.ru.md),
   [HTTP 503 handoff](docs/HTTP_503_HANDOFF.ru.md), previous project session notes in Git history.

## 3. Baseline and non-negotiable constraints

- PR 1–9 delivered the existing domain, scoring, rooms, controls, ranking, media
  and release candidate. Public catalog card is visible. Owner reports the game
  now works; this is not independent production/UAT or quota verification.
- Preserve HTTP 503 SDK repair (`ref.get(transaction=tx, timeout=5.0)`) and
  safe diagnostics. Historical IAM/account uncertainty and outstanding UAT must
  not be treated as resolved without evidence. Prior standalone foundation
  checker reported a binary WebP raw-Cyrillic false positive; reproduce first.
- One embedded monorepo, existing Next.js/Vercel + FastAPI/Render + Firestore;
  no paid services, no paid TURN or managed TTL, no billing/IAM changes.
  Three humans, normal meetings 4–6h twice monthly; engineering reserve 8h.
  Target commit-to-opponent p95 <= 500ms on stable warm connections, <=15k reads
  and <=10k writes per 6h room session. These targets require measurements.
- Existing auth/grants, role/seat isolation, authoritative transactions,
  idempotency, append-only audit and immutable results. Never serialize private
  GameState or opponents' hidden cards into HTTP, WS, DOM, logs or recordings.
- Keep game commands on existing authenticated HTTP BFF; proposed narrow Render
  WSS exception needs an ADR and secure short-lived one-use ticket, Origin and
  membership checks, revocation, bounded queues, single-worker/topology review,
  fallback and restart tests. No raw token in URL; no hard-coded backend host.
- Remove ordinary heartbeat writes, not durable game commits. Separate
  presentation version, pause reasons and game version; freeze timers on pause,
  preserve remaining time, never resume while another pause reason exists.
- 2D table, own cards bottom, left=(seat+1)%3, right=(seat+2)%3; Russian classic
  deck, red patterned backs; landscape phone only, accessible portrait guidance.
  Shared score sheet, radio, last trick and replayable public widow; one open
  object, any seated player closes. Last trick closes atomically on next legal
  play; break resumes on all three ready; next deal 5s after complete settlement.
- Music controls shared, volume local, approved/licensed tracks only; reconnect
  catches up without interrupting others. WebRTC is optional, no paid relay.
  Unanimous recording consent, fail-closed withdrawal, only public scene,
  direct local disk or playable bounded segments; no unbounded Blob array.
- Russian content in `*.ru.*` files or Unicode escapes; this handoff stays in
  English. Project-local source, scoped CSS, existing shared packages/host
  adapters only. Do not touch other project domains or public site behavior.

## 4. Delivery ledger

| Stage | Branch | Status | Next gate |
|---:|---|---|---|
| 10 | `feat/preferans-realtime` | PLANNED / authorization pending | 10.A baseline and transport ADR |
| 11 | `feat/preferans-game-table` | PLANNED | PR10 merge; approve local interactive mockup |
| 12 | `feat/preferans-game-interaction` | PLANNED | PR11 merge; full deal flow |
| 13 | `feat/preferans-shared-room` | PLANNED | PR12 merge; shared pause/audio/media |
| 14 | `feat/preferans-modernization-release` | PLANNED | PR13 merge; real acceptance and quota evidence |

Five stages, one PR per stage, roughly 14–17 working commits including docs.
Squash merge after Owner review/hosted checks. Stage numbers are not GitHub PR IDs.
Do not advance to the next stage without Owner instruction and updated main.

## 5. Open work / risks

- PR10: inventory actual implementation vs original requirements, including
  admin-only room creation, lobby readiness/list, sheet-discard, punch choice,
  rule sets, accidental reveal voting; assign gaps across PR11–14. Do not hide
  missing workflows behind UI or rewrite historic results. Old unresolved rule
  examples: forced-suit passout fallback, timer reference on passouts, tied last
  loser; inspect later evidence before asking a focused Owner question.
- Confirm actual free-tier configuration/shared daily usage, worker topology,
  secure realtime authorization and baseline metrics; do not claim a cost SLA.
- PR11: approved local table prototype and asset provenance. PR13: music rights,
  actual browser file-writer support, NAT and consent-safety evidence. PR14: real
  three-account/device, 6h/8h soak, privacy, quotas and rollback acceptance.
- Existing core may be live; do not change production flags from historical
  notes. New features gated, compatible old clients, safe rollback; Owner approves
  release separately. Green CI is not full UAT.

## 6. Compact checkpoint — update after each verified slice

- Date / current branch / base main SHA: 2026-11-24 / planned PR10 / `93611d3`.
- Owner authorization: documentation only; implementation pending.
- Completed: requirements and delivery plan prepared; no product implementation.
- Verification: repository/source inspection; provider documentation review.
  No product CI, emulator, load, browser or production acceptance run for this handoff.
- Last working commit / status: Owner to fill after saving docs; no Git mutations
  by the author of this ZIP. Re-check local state before any work.
- Decisions/risks: see MOD-TZ sections 4–6, 11–14 and plan 10.A.
- Next smallest deliverable: after authorization, baseline/ADR/gap register.
- STOP: do not start implementation, create PRs, deploy or enable flags now.

Replace this compact checkpoint after a tested slice; record exact commands,
PASS/FAIL/SKIPPED, actual commit/dirty state, ADR decisions and next task.
Never fabricate test/merge/deploy status. This is a human handoff, not a CI/build
contract; do not introduce checks of its existence, title or hash.
