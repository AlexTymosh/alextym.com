# Preferans — Session Notes

**Project ID:** `preferans`
**Site route:** `/portfolio/preferans`
**Folder:** `portfolio/preferans/`
**Version:** 1.4 / 2026-11-23
**Delivery:** 9 PRs, about 20 meaningful working commits; squash merge each PR.

## 1. Current status (verified 2026-11-23)

- **PR 1** [#268](https://github.com/AlexTymosh/alextym.com/pull/268): merged `e7a2a6d`.
- **PR 2** [#269](https://github.com/AlexTymosh/alextym.com/pull/269): merged `59c60cd7`.
- **PR 3** [#270](https://github.com/AlexTymosh/alextym.com/pull/270): merged `9d46a8fdcc4d6e932aa788e23a8918dfc6f64939`.
- **Current PR 4:** `feat/preferans-secure-rooms` — authenticated FastAPI room API, Firestore transactions, BFF, safe projections, idempotency.
- **Confirmed house decisions:** 1B simultaneous passout rewards, 2A auto-win resets passouts, 3A remaining positive points after hill payment enter own open pool. See `docs/HOUSE_RULES_DECISIONS.ru.md`.
- **Gate:** `PREFERANS_ROOMS_ENABLED=false` by default; no production game enabled, no client Firestore rules changed.
- **Testing:** author sandbox Python tests only. Local full `task ci`, hosted GitHub CI and Firebase emulator integration remain unverified until user executes them.

## 2. Next action (PR 4)

1. Apply the reviewed ZIP on a fresh branch from `main` after #270; do not overwrite user files.
2. Run `uv lock` in backend, include `backend/uv.lock` in commit; format and test; run all `task ci` checks.
3. Commit code in two stages (domain/rooms and host/BFF wiring), then docs/testing; push and manually open PR.
4. Verify all GitHub CI jobs, Docker installation and Firebase Auth/Firestore emulator against real transactions.
5. **Do not enable** new room API in production before direct-Render authorization, three-browser privacy, idempotency and reconnect UAT pass.
6. After squash merge start PR 5 for the actual responsive three-player table UI.

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
| 4 | secure-rooms | Auth + Firestore + realtime spike | IN DEVELOPMENT | PR 4 package; CI pending |
| 5 | game-ui | Full three-player table/UI | PLANNED | — |
| 6 | game-controls | Timer, votes, admin adjustments | PLANNED | — |
| 7 | history-ranking | Stats, ranking, graphs | PLANNED | — |
| 8 | media | WebRTC, consent, local recording, interior | PLANNED | — |
| 9 | release | Security/performance/regression/documentation | PLANNED | — |

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
