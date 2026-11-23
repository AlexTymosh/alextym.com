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
