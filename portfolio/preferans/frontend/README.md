# Preferans frontend

Use the host's React/Next.js dependencies and the public `@preferans` entry only. UI components and CSS Modules live under `src/`; never import another portfolio project's internals or global styles.

`src/content.ru.json` contains Russian UI strings under a repository-allowed filename. The PR 1 shell is informational only; no fake interactive game behavior is present.

## PR 5 interactive table

`PreferansGame.ru.tsx` now provides the guarded browser game UI, with `game-model.ru.ts`,
`room-client.ts`, and a dedicated CSS Module. The Next.js page serves this game only
when `PREFERANS_ROOMS_ENABLED=true`; otherwise it keeps the informational shell.
All actions go to the existing protected Next.js BFF; there is no direct browser
Firestore SDK access. No persistent storage of private card order or hand data.
See `../docs/PR05_GAME_UI.ru.md` and `../docs/PR05_UAT.ru.md`.


## PR 6 game controls

`PreferansControls.ru.tsx` provides an accessible undo/counter/adjustment panel and a numeric lobby policy editor. The client sends `pulse` heartbeats while playing, displays the **server-issued** countdown and does not calculate or apply financial penalties. All mutations go through the existing protected BFF with idempotency and current versions. See `../docs/PR06_GAME_CONTROLS.ru.md` and `../docs/PR06_UAT.ru.md`. HTTP-based offline presence is approximate, not an instant presence guarantee.


## PR 7 ranking and history

`PreferansHistory.ru.tsx` provides the sortable materialized ranking table, recent immutable result list and a graph of three explicitly chosen participants. `history-model.ts` contains pure sorting, timestamp ordering and API payload validation. The browser receives only server-allowlisted results and opaque identifiers; Firebase UID and hidden game state remain on the server. The 100-game history window can be incomplete; the UI says so. Read `../docs/PR07_HISTORY_RANKING.ru.md`.
