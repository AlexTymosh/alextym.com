# Preferans — Session Notes

**Project ID:** `preferans`
**Site route:** `/portfolio/preferans`
**Folder:** `portfolio/preferans/`
**Version:** 1.9 / 2026-11-24
**Delivery:** 9 PRs, about 20 meaningful working commits; squash merge each PR.

## Current checkpoint — Firestore HTTP 503 repair (2026-11-24)

- Latest verification: the Owner reports the checks are now green after the
  requested rerun. The new run logs were not independently inspected by the
  agent; the earlier agent-run network failure below remains historical evidence.
- Work uses the user-selected existing `feat/preferans-release` from `69a8ece`.
  No commits, push, PR, deploy, IAM changes or production writes were performed.
- Confirmed SDK defect and a separate checked-account IAM blocker: the known
  Render runtime principal lacks query,
  transaction and create/update IAM permissions; `_get()` treated the real
  Python SDK generator as a document snapshot. The current local runtime key
  reads a real document, but both Preferans queries return `PermissionDenied`.
  The Owner is unsure which account is in the current Render secret and the MCP
  did not read it. Production history/ranking root cause is therefore not fully
  established: match `client_email` or inspect new safe logs after deployment
  before applying the IAM correction. Do not assume this account is active.
- Fixed `ref.get(transaction=tx, timeout=5.0)`, corrected Fake transaction/query
  semantics and added safe operation/type/stage/request-ID diagnostics.
  No auth/grant, client rule, data schema or dependency changes.
- Executed: `task repo:check`; `task backend:check` (1327 passed, 8 optional
  skipped); `task frontend:check` (444 passed, 50 mode-specific skipped);
  four real Auth/Firestore Emulator tests and 17 local HTTP assertions through
  the real Next.js BFF. `task ci`: 7/8 PASS; the frontend phase had one mobile
  Resume `page.goto` failure (`net::ERR_ADDRESS_IN_USE`), 443 passed/50 skipped.
  That exact test passed separately on an isolated localhost port outside the
  network sandbox, with one worker, zero retries and no code changes. The full
  CI invocation is recorded as failed, not retroactively green.
- Live read-only guest checks returned 401 for history/rankings on both the
  site and direct Render origin (four requests). Authenticated production
  recovery still requires IAM correction and deployment.
- If the checked principal is confirmed active, the operator must add only
  `datastore.entities.list`, `datastore.databases.get`,
  `datastore.entities.create`, `datastore.entities.update` to the existing Render
  runtime role, preserving current permissions, then deploy and verify production
  201/200 and 401/403. Neither IAM nor production recovery is claimed complete.
- Emulator lock contention can exhaust the SDK's five attempts; tests preserve
  this real 503 and verify a subsequent request cannot duplicate the room.
- Evidence, complete 503 inventory, commands and deployment limitations:
  [HTTP 503 investigation and runbook](docs/HTTP_503_FIRESTORE.ru.md).
  [Owner handoff](docs/HTTP_503_HANDOFF.ru.md) contains PowerShell test/commit
  commands and ready English PR/squash text; no Git mutations were performed.

The checkpoints below are historical; this repair does not sign off media,
full house rules or three-device production UAT.

## 1. Current status (verified 2026-11-23)

- **PR 1** [#268](https://github.com/AlexTymosh/alextym.com/pull/268): merged `e7a2a6d`.
- **PR 2** [#269](https://github.com/AlexTymosh/alextym.com/pull/269): merged `59c60cd7`.
- **PR 3** [#270](https://github.com/AlexTymosh/alextym.com/pull/270): merged `9d46a8fdcc4d6e932aa788e23a8918dfc6f64939`.
- **PR 4** #271: merged `622d1831`; **PR 5** #272: merged `595f8b7f`.
- **PR 6** #273: merged `008ee18e`; **PR 7** #274: merged `4f88428e`; **PR 8** #275: merged `bae66e25`; **current PR 9:** `feat/preferans-release` — release candidate hardening, zero-cost retention controls and UAT.
- **Confirmed house decisions:** 1B simultaneous passout rewards, 2A auto-win resets passouts, 3A remaining positive points after hill payment enter own open pool. See `docs/HOUSE_RULES_DECISIONS.ru.md`.
- **Gate:** `PREFERANS_ROOMS_ENABLED=false` remains the default. The Owner reports it enabled on Render during this incident; current production activity must not be inferred from older release notes. Client rules are unchanged.
- **Testing:** executed local checks are recorded above. Hosted GitHub CI, production recovery and broader multiplayer/media UAT remain separate gates.

## 2. Next action (PR 9)

1. Install PR9 patch on a clean branch based on merged PR #275 SHA `bae66e25`.
2. Run `task repo:check`, backend/frontend checks and `task ci`; all five GitHub CI jobs are required.
3. Run real Auth/Firestore Emulator three-player UAT including denied grants, direct backend access and hidden-card projection checks.
4. Run three physical-device WebRTC recording/consent test and measure Firestore quota; media remains off in production until acceptance.
5. Strict £0: **do not enable paid Firestore TTL deletes**. Use documented bounded operator cleanup and record residual retention risk.
6. PR9 is a release candidate, not Owner sign-off. Resolve missing house-rule workflows before promising full functional parity.

## 3. Decisions not to revisit without evidence

- One existing monorepo, existing Vercel + Render, **no new paid services**.
- Project owned UI/backend/docs/tests, host-owned adapters only. No Fleet or Workforce domain imports.
- Existing Firebase Portfolio Lab auth + per-project grants; Owner controls access.
- Three authenticated humans; game admin is NOT global Owner; Owner is room admin by default.
- Durable Firestore game state, server-authoritative deterministic Python game engine.
- Hidden cards never in public views, logs, or other players' projections.
- Full game specs in `docs/FULL_TECHNICAL_SPECIFICATION.ru.md`; player rules in `docs/HOUSE_RULES.ru.md`; this is a **handoff**, not an alternate ruleset.
- Trading is a **minimum bid**, final contract is a separate event after widow; special bids, "here" (except 6 spades), penalties in referenced specs.
- Each game captures immutable ruleset snapshot; finish is immutable; admin corrections have append-only audit while active.
- Russian game UX, public English card; filenames `*.ru.*` for Cyrillic (repo policy).
- No server-side video storage; 3-party consent before local recording. TURN under strict £0 is a release risk, not silently solved.

## 4. Runtime and security gates

- Page must be hidden when Portfolio Lab is disabled; with Lab enabled, require explicit `preferans` project grant. A catalog entry **never grants access**.
- No live Preferans API in PR 1. Before adding one: enforce direct Render authentication, project/room permissions, no cross-project access, idempotent Firestore transactions.
- Firestore projection approach is a PR 4 spike; inspect client Firebase Auth persistence across page reload, otherwise consider authorised BFF/SSE.
- Server persists absolute timer deadlines; clients only display countdown; reconnect/restart must not lose a game.
- No `View` writes, no debug endpoint exposing room secret state, no real user UID or Firebase secret in Git.
- Verify CI: project, backend, frontend, rag, docker. Do not mark green without executed results.

## 5. Work packages and merge states

| PR | Branch suffix | Scope | Status | Last evidence |
|---:|---|---|---|---|
| 1 | foundation | Registration, guarded shell, docs | MERGED | PR #268, `e7a2a6d` |
| 2 | engine | Pure Python auction, cards, play | MERGED | PR #269, `59c60cd7`, CI green |
| 3 | scoring | Ledger, rulesets, golden fixtures | MERGED | PR #270 `9d46a8f` |
| 4 | secure-rooms | Auth + Firestore + realtime spike | MERGED | PR #271 `622d1831` |
| 5 | game-ui | Full three-player table/UI | MERGED | PR #272 `595f8b7f` |
| 6 | game-controls | Timer, votes, corrections | MERGED | PR #273 `008ee18e` |
| 7 | history-ranking | Final results, medals, charts | MERGED | PR #274 `4f88428e` |
| 8 | media | WebRTC/recording/interior | MERGED | PR #275 `bae66e25` |
| 9 | release | Privacy, retention, regression/UAT | IN DEVELOPMENT | PR9 package |

## 6. How to resume in a new coding session

Read in this order:

1. `portfolio/preferans/SESSION_NOTES.md` (this file; verify status is up to date).
2. `portfolio/preferans/docs/DEVELOPMENT_PLAN.ru.md` — active PR section and gates.
3. `portfolio/preferans/docs/FULL_TECHNICAL_SPECIFICATION.ru.md` — only relevant spec sections.
4. `portfolio/preferans/docs/HOUSE_RULES.ru.md` — rules as users see them.
5. `docs/architecture/portfolio.md` and Portfolio Lab auth/grants contract.
6. `git status --short`, `git log -5 --oneline`, current `main`, recent PR CI and deployment evidence.

**Checkpoint template:**

```text
Date / branch / base main SHA:
PR and last commit SHA:
Implemented (commit-scoped):
Tests executed (exact commands + PASS/FAIL):
Not tested / missing setup:
New risks and spec decisions (ADR link):
Next smallest deliverable:
```

Never mark a PR as merged, deployed, tested or complete based only on code appearance or this plan.

## 7. PR 2 implementation notes

- `preferans.domain.cards`: 32-card deck, 2-card packets, widow position, immutable hands, OS-backed shuffle.
- `preferans.domain.auction`: all 32 ranked bids, first-hand `here` excluding 6 spades, special bids and immutable auction events; bid is a minimum, not final contract.
- `preferans.domain.game`: explicit DISCARD/DECLARE/DEFENSE/PLAY stages; one-vister open/dark choice after first declarer lead; normal ten-trick completion, passout first-three lead override.
- `preferans.domain.play`: follow suit, compulsory trump, optional overtrump, forced widow suit on the first two passout tricks.
- Financial settlement, undo, media, Firebase, Firestore, realtime and player-view projection are **not** part of PR 2.
- A forced-suit passout trick with zero cards of that suit uses an **explicit provisional fallback** to the actual led suit; user confirmation is needed before production game acceptance. See `docs/DOMAIN_ENGINE.ru.md`.
- Never expose or serialize `GameState` directly to the browser; it contains all private hands, hidden widow and discarded cards.

## 8. PR 3 implementation checkpoint

- New pure modules: `rulesets.py`, `ledger.py`, `scoring.py`, `settlement.py`.
- Game engine adds `WITHOUT_THREE` concession before the first card only.
- Exact formulas and explicit rule assumptions: `docs/SCORING_ENGINE.ru.md`.
- Three new scoring test files run through the existing backend test directory.
- Pending: user-run `task ci`, GitHub review, PR URL, merge hash, confirmation of open rules.

## PR 5 checkpoint (2026-11-23)

- **PR 4** [#271](https://github.com/AlexTymosh/alextym.com/pull/271) was squash-merged into `main` at `622d1831d8ccc40e4dea701da0abc4a6ce78429d`.
- **Active PR 5:** `feat/preferans-game-ui`, accessible lobby + invite/join, 3-seat table, complete action controls, restricted projections, polling/reconnect, scoring panel and responsive card sorting.
- **Required production gates:** actual Firebase Auth/Firestore emulator three-user test, signed auth/grant isolation including direct Render, and `task ci` + all five GitHub jobs. No claim of live multiplayer readiness without these tests.
- **New API:** Test/Admin-only invitation envelope exposes lobby occupancy/version but no UID or private state.
- **PR 6** remains planned for timer, undo voting, and audited corrections; **PR 8** for WebRTC media.

## PR 6 checkpoint (2026-11-23)

- **PR 5** [#272](https://github.com/AlexTymosh/alextym.com/pull/272) merged to `main` at `595f8b7f251832c912cc3fab524fe63d6a216188` on 2026-11-23 14:29 UTC. PR 1–5 are now merged.
- **Active PR 6:** `feat/preferans-game-controls`, server-clock counter + auto repeat, two-person undo votes, private pre-move checkpoint, heartbeat-based conservative pause, numeric lobby policy and audited corrections.
- **Tests in isolated author fixture:** 280 Preferans Python tests pass, TypeScript source typecheck with temporary stubs passes, compileall passes. Real CI, real Firestore transactions and 3-user production UAT are NOT verified.
- **Storage:** existing deny-all client Firestore rules unchanged; all controls in `private/current`, append-only nonsecret room events. Public view is explicitly projected, not serialized from the hidden snapshot.
- **Limitations:** heartbeat detection cannot instantly prove disconnect, no full historical numerical ruleset editor, unintentional card exposure vote and manual reconciliation of specific `ledger_entry_id` are deferred. See `docs/PR06_GAME_CONTROLS.ru.md`.
- **Remaining:** PR 7 (immutable history/medals/rankings); PR 8 (opt-in WebRTC + local recording + nostalgic backdrop); PR 9 (security, offline fidelity, Firestore quota, performance/accessibility/UAT and release).


## PR 7 checkpoint (2026-11-23)

- Verified PR #273 merged into main SHA `008ee18ee2b27f2c1fb8d7a15506a140090003e0`.
- Active PR 7: immutable one-per-room `GameResult`, atomic per-player rankings, public project-grant-protected history endpoints and chart.
- Historical Firebase UIDs and hidden hands are NOT serialized into results. Unknown pre-PR7 start time remains `null`.
- Isolated Python tests and TypeScript source checks are not substitutes for GitHub CI or real Firestore transactions.
- Known release gaps: confirmed punch conversions, accepted sheet-discard workflow, full pause durations, display names, three-browser UAT. See `docs/PR07_HISTORY_RANKING.ru.md`.

## PR 8 checkpoint (2026-11-23)

- Verified PR #274 merged to `main` SHA `4f88428e539fbe979f407d83f617ebc76a3b33d4`.
- PR8 introduces backend-only Firestore media signals, optional client WebRTC mesh and local-only canvas/audio recording by the initiator after three approvals.
- Separate media feature gates off by default; source files and local artwork are isolated under `portfolio/preferans`.
- Tests: isolated Python fake-DB + focused TypeScript check are not equal to real Firebase Emulator or device UAT.
- Blocking risks: no TURN guarantee, near-real-time rather than hard instant revocation, Firestore retention/quota, browser recording codec and audio-mixing compatibility.
- PR 9 must close these gaps or explicitly remove noncompliant recording from release. See `docs/PR08_MEDIA.ru.md`, `docs/PR08_UAT.ru.md`.

## PR 9 checkpoint (2026-11-23)

- Verified PR #275 was merged to main SHA `bae66e255f1e3a4a39a41f4c217c23545568a0eb`.
- Introduces fail-closed local recording watchdog, explicit expiry metadata, unique Preferans media collection groups and a bounded manual cleanup script.
- Firebase Firestore TTL deletes require billing and **must NOT be enabled** under the no-paid-services rule. Metadata alone does not delete documents.
- Isolated Python/type checks are not full browser/UAT or GitHub CI. Media and room feature flags remain disabled in production until sign-off.
- `docs/PR09_RELEASE_CANDIDATE.ru.md`, `docs/PR09_UAT.ru.md` define operation and acceptance. Known gaps: sheet-discard workflow, punch substitution, full house rules editor, accidentally exposed card vote, live 3-device media and quota measurements.
