# Preferans — Session Notes

**Project ID:** `preferans`
**Site route:** `/portfolio/preferans`
**Folder:** `portfolio/preferans/`
**Version:** 1.0 / 2026-11-22
**Delivery:** 9 PRs, about 20 meaningful working commits; squash merge each PR.

## 1. Current status (update after every meaningful commit)

- **Baseline inspected:** `AlexTymosh/alextym.com`, `main`, 2026-11-22; Git tree SHA `491a909c65dbbecf0110d600c9d9516cf2e84d65` (not a commit SHA). Recheck latest HEAD before applying patch.
- **Active PR:** PR 1, foundation, **patch prepared but not applied to user's repository**.
- **Branch to create:** `feat/preferans-foundation`.
- **PR URL / number:** not created.
- **Latest local commit SHA:** none.
- **Latest merged squash SHA:** none.
- **Tests actually executed in user's repo:** none. Temporary fixture checks do not establish GitHub CI results.
- **Deployments / Firebase migrations:** none.

## 2. Next action

1. On Windows 11, update `main`, verify clean `git status`, create `feat/preferans-foundation`.
2. Extract ZIP, execute `apply.ps1 -RepoRoot <repository path> -ExpectedBranch feat/preferans-foundation`.
3. Run `verify.ps1` and the repository's `task repo:check`, `npm` frontend checks, then `task ci` with correctly configured toolchain.
4. Inspect staged diff; make PR 1's **two meaningful commits** (first code/registration, second docs and handoff).
5. Push branch, open PR with `PR01_HANDOFF.ru.md`, review CI (all five jobs) and protected-route behavior; squash merge only when passing.
6. Update this document with actual PR number, checks, SHA and new risks, then create PR 2 branch from updated `main`.

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
| 1 | foundation | Registration, guarded shell, docs | PATCH READY; NOT APPLIED | ZIP bundle and local patch fixture |
| 2 | engine | Pure Python auction, cards, play | PLANNED | — |
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
