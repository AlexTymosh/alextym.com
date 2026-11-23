# Preferans — Session Notes

**Project ID:** `preferans`
**Site route:** `/portfolio/preferans`
**Folder:** `portfolio/preferans/`
**Version:** 1.1 / 2026-11-23
**Delivery:** 9 PRs, about 20 meaningful working commits; squash merge each PR.

## 1. Current status (update after every meaningful commit)

- **Merged PR 1:** [#268](https://github.com/AlexTymosh/alextym.com/pull/268), squash SHA `e7a2a6dd519b852d2c640cb7d1b8170f89baec4a`, on `main` 2026-11-23.
- **PR 2:** `feat/preferans-engine` — pure Python domain engine, awaiting the user's local application, CI verification, push and PR.
- **PR 2 base:** `e7a2a6dd519b852d2c640cb7d1b8170f89baec4a` (PR 1 merge). Verify fresh `main` before applying.
- **PR 2 current local commit SHA:** not yet committed; update after user creates commits.
- **PR 2 GitHub PR number:** not yet opened; update after push.
- **Authoring sandbox validation:** 184 targeted pytest cases passed; Python compilation passed. This is NOT a result from the user's monorepo/CI.
- **Host CI:** not yet executed for PR 2. Require five GitHub jobs before merge: project, backend, frontend, rag and docker.
- **Public game API, Firestore game data and production gameplay:** not implemented.

## 2. Next action (PR 2)

1. In Windows PowerShell, pull merged `main`, verify clean working tree, create `feat/preferans-engine` from it.
2. Extract `preferans-pr02-engine.zip`; run provided `apply.ps1`, which preflights paths, branch, base commit and file hashes before changing the worktree.
3. Format **only** new Preferans Python source/tests with Ruff; run targeted tests, repository checks and `task ci`.
4. Review diff; create two meaningful commits (engine/tests; CI wiring/documentation); push and open PR 2.
5. Verify protected existing site behavior and all five GitHub CI jobs. Squash merge to `main` only after green evidence.
6. Record final PR URL, squash SHA, exact executed tests and any remaining rules assumption; start PR 3 from updated `main`.

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
| 2 | engine | Pure Python auction, cards, play | CODE PACKAGE READY; NOT MERGED | 184 sandbox pytest cases; host CI pending |
| 3 | scoring | Ledger, rulesets, golden fixtures | PLANNED | — |
| 4 | secure-rooms | Auth + Firestore + realtime spike | PLANNED | — |
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
