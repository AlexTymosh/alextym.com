# Zaporizhzhia Preferans — portfolio module

**Status: PR 2 pure game domain engine added. No live game API, Firestore writes, UI gameplay or media yet.**

- Project ID: `preferans`
- Private route: `/portfolio/preferans`
- Reserved API prefix (not mounted): `/api/preferans`
- Public portfolio card: disabled (`catalog.visible=false`)
- PR 1: merged as #268; PR 2 branch: `feat/preferans-engine`

## Boundaries

The website owns authentication, project grants, the guarded Next.js adapter and build/deploy wiring. Preferans owns its UI, future deterministic game domain, data schema, room rules, and tests. No direct Fleet/Workforce imports, separate credentials or standalone deployment.

`frontend/` hosts the project-owned React components and locally scoped CSS. `backend/src/preferans/domain/` contains a pure, side-effect-free rules engine. There are **no** live Preferans API routes or persistence adapters; those require separate protected integration. `tests/` now contains the original foundation guard and deterministic Python engine tests. `docs/` holds both specifications and the engine contract.

## Read before writing code

1. [`SESSION_NOTES.md`](SESSION_NOTES.md)
2. [`docs/DEVELOPMENT_PLAN.ru.md`](docs/DEVELOPMENT_PLAN.ru.md)
3. [`docs/FULL_TECHNICAL_SPECIFICATION.ru.md`](docs/FULL_TECHNICAL_SPECIFICATION.ru.md)
4. [`docs/HOUSE_RULES.ru.md`](docs/HOUSE_RULES.ru.md)
5. [`docs/DOMAIN_ENGINE.ru.md`](docs/DOMAIN_ENGINE.ru.md)
6. [`../../docs/architecture/portfolio.md`](../../docs/architecture/portfolio.md)

## Focused checks (repo root)

```bash
node scripts/check-portfolio-registry.mjs
node scripts/check-registered-project-boundaries.mjs
node portfolio/preferans/tests/check-foundation.mjs
node scripts/check-no-raw-cyrillic.mjs
task repo:check
# from backend/: uv run python -m pytest ../portfolio/preferans/tests -q
```

The raw Cyrillic check examines tracked files; stage newly added files before relying on its result. Run the entire `task ci` before PR review. No successful CI result is claimed by this README.

## Access

The route returns 404 if Portfolio Lab is disabled. When enabled, the shared project-grant check allows only granted users (Owner inherits access). The shell does not expose rooms, player data, cards, game APIs or secrets. Further controls and endpoints require additional backend protection and review.

## PR 4 — private rooms (feature gated)

The room API is implemented behind `PREFERANS_ROOMS_ENABLED=true`; default is disabled. It uses Firebase Portfolio Lab access, transactional server-only Firestore storage, strict per-player projections and idempotent command receipts. The browser has no direct Firestore read/write access. See `docs/SECURE_ROOMS.ru.md`, `docs/HOUSE_RULES_DECISIONS.ru.md`, `docs/PR04_RUNBOOK.ru.md`. The interactive table is still planned for PR 5.

## PR 5 — private interactive game UI

With the Portfolio Lab and Preferans room feature flags enabled, the project page
now offers a responsive three-player table. Firestore remains server-only;
`View` users cannot create/join games. See `docs/PR05_GAME_UI.ru.md`.
The flag is off by default; no existing public website routes change.
