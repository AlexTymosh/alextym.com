# Preferans — session notes

Version 2.1 | 2026-11-24 | Project only. Root SESSION_NOTES unchanged.

## Current checkpoint
- Modernization PR10: `feat/preferans-realtime`; inspected main `93611d3ea7c67a5762888c6ed17bd146406d7d4c`. Candidate ZIP; not merged or deployed. Owner must run repository CI and staging acceptance before enabling realtime.
- Owner scope correction: video recording is excluded from modernization (UX-08, NFR-12, AV-02/03 retired). Keep live voice/video for PR13. Do not develop recorder, file writer, segmentation or recording soak. Legacy recording implementation remains untouched by PR10; do not expose it in the new scene.
- Read `docs/MODERNIZATION_TECHNICAL_SPECIFICATION.ru.md`, then active section of `docs/MODERNIZATION_DEVELOPMENT_PLAN.ru.md`, `docs/ADR_REALTIME_TRANSPORT.ru.md`, `docs/PR10_REALTIME_RUNBOOK.ru.md`, `docs/MODERNIZATION_GAP_REGISTER.ru.md`. Original HOUSE_RULES and FULL_TECHNICAL_SPECIFICATION still govern all unchanged rules. Earlier notes remain in Git history.
- PR10: protected one-use ticket, seat-only WS snapshots after commit, HTTP commands, bounded in-memory presence and retry, fallback, independent pause reasons, conservative recovery and process-local counters. No table redesign, overlay UI, automatic deal or live-media rewrite yet.
- Single Render instance AND single Uvicorn worker are mandatory. Observed free Docker service with one instance; runtime worker env not verified. Feature gates default off; no deployment/env/production data modified. Existing HTTP 503 SDK fix and IAM diagnostics must survive. See `docs/HTTP_503_FIRESTORE.ru.md` and `docs/HTTP_503_HANDOFF.ru.md`.
- Verification in packaging environment: 10 hub/clock tests passed (including simulated 4,320 heartbeats), 2 ASGI tests passed with a temporary fake storage adapter, isolated TypeScript contract check passed with a stub for the existing view type. Full source clone was unavailable; actual patched repository build, Ruff, store integration tests, Playwright, Firebase emulator, quota/latency and real devices remain pending. Never label the candidate production-ready on this evidence.
- Next action: apply on PR10 branch, run scoped tests and full `task ci`, fix any failure without suppressing checks, then Owner reviews PR and squash merges. Document exact results. Enable only after separately approved staging UAT; retain fallback and rollback gates.

## Upcoming PR boundaries
- PR11 `feat/preferans-game-table`: interactive layout/prototype, Russian atlas cards, seats, avatars, landscape, lobby/access gaps assigned in register.
- PR12 `feat/preferans-game-interaction`: auction, hand, widow, tricks, animation, automatic next deal; preserve domain.
- PR13 `feat/preferans-shared-room`: synchronized objects, break, score sheet, menu, permitted music, optional live WebRTC. No recording.
- PR14: functional gaps, security, 6/8-hour acceptance, measurements, release gate.
- Do not start next PR without Owner instruction. Start from updated main after merge; preserve project isolation, existing project grants, public English card and private Russian game. No paid services/billing/TTL/TURN. No raw private state or credential logs. No speculative changes to historical rules.

## Checkpoint protocol
After each meaningful slice: branch/base, changed files and behavior, actual commands/results, failures/untested items, next smallest task. Update this project note only; do not make its existence/hash a build contract. Commit only relevant files; retain audit and historical records. No fabricated CI/deploy/measurements. Check root AGENTS.md and applicable host docs before editing host adapters.
