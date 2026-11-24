# Preferans — session notes

Version 2.2 | 2026-11-24 | Project only. Root SESSION_NOTES unchanged.

## Current checkpoint
- PR10 is merged; inspected `main` SHA `2166e10cbcff19e743556917e000671cead87ba5`. Owner reports all CI tests green. Production realtime activation, topology, live latency/quotas and three-device acceptance have not been verified in this session. Do not change feature flags or payment settings.
- Owner authorized PR11 (`feat/preferans-game-table`) only. Candidate overlay includes original atlas-inspired SVG deck, three-seat table geometry, current trick and public widow, independent presence and turn/controller indicators, lazy project menu, mobile landscape/portrait prompt, bounded room directory, room-member profile projection and new-room unanimous readiness/configuration. Existing authoritative commands and PR10 transport preserved. No game-rule changes. Original prototype is offline and synthetic; review it before merge.
- First deal of newly API-created rooms requires each occupied seat to confirm roster, dealer, pool target, rules and policy. Admin/Owner can create; project Test can join. Existing lobbies created before PR11 remain compatible. Full seat swap, prior-loser selection for a later new session, full presets/editor and archive remain gaps; do not claim full lobby parity. Stored uploaded WebP and explicitly stored names only; provider avatars and video tiles deferred. Unknown presence is gray, not fabricated green. Legacy media in menu is live-only UI; recording is not part of modernization.
- Implemented candidate against exact main anchors; pure TS checks (54 assertions with structural contract fixture), 33 SVG XML checks, offline Chromium layout and perspective checks passed. Full repository clone, SDK/emulator tests, actual Next build, Ruff/CI and authenticated browser UAT not executed here. Owner must run format.ps1 and verify.ps1. Do not mark merged until independently checked or reported by Owner.
- Read `docs/MODERNIZATION_TECHNICAL_SPECIFICATION.ru.md`, active PR11/PR12 section of `docs/MODERNIZATION_DEVELOPMENT_PLAN.ru.md`, `docs/PR11_GAME_TABLE.ru.md`, `docs/MODERNIZATION_GAP_REGISTER.ru.md`, `docs/ASSET_LICENSES.ru.md`. Original house rules remain authoritative except explicitly approved modernization changes. Preserve HTTP 503 repair and PR10 realtime/rollback runbooks.

## Next work boundary
- Review `table-preview.html` before merging PR11. Run repo CI and tests; review actual game with three authenticated users and both host themes; record exact results. Do not enable billing, paid TTL, TURN, or any recording work.
- PR12 `feat/preferans-game-interaction`: real two-step auction and final contract, own/open hand decisions, sorted hand preferences, widow visibility/replay, animations and automatic next deal. Preserve existing deterministic domain logic.
- PR13: synchronized shared objects, score sheet, music, break, live WebRTC tiles only, no recording. Independent pause reasons and synchronized state; never replace server controls with a local overlay. PR14 functional gaps and 6/8-hour acceptance.
- Start next branch only from updated main after merge and explicit Owner instruction. Commit/push/PR/merge performed by Owner. Never touch unrelated project notes or RAG.

## Checkpoint protocol
After each slice: branch/base, exact changed behavior, executed commands and results, untested items, risk and next smallest task. Project notes are a human handoff, not a CI/build contract. Never invent CI/deploy evidence. No UID/email/token/hidden cards in public projections or logs.
