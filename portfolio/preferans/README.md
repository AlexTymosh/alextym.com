# Zaporizhzhia Preferans — portfolio module

**Status: foundation only. Gameplay, backend API, Firestore writes and media are NOT implemented.**

- Project ID: `preferans`
- Private route: `/portfolio/preferans`
- Reserved API prefix (not mounted): `/api/preferans`
- Public portfolio card: disabled (`catalog.visible=false`)
- Branch (PR 1): `feat/preferans-foundation`

## Boundaries

The website owns authentication, project grants, the guarded Next.js adapter and build/deploy wiring. Preferans owns its UI, future deterministic game domain, data schema, room rules, and tests. No direct Fleet/Workforce imports, separate credentials or standalone deployment.

`frontend/` hosts the project-owned React components and locally scoped CSS. `backend/` is deliberately only a placeholder until a protected FastAPI module is implemented. `tests/` contains static foundation checks. `docs/` contains the implementation plan, full spec, and house rules.

## Read before writing code

1. [`SESSION_NOTES.md`](SESSION_NOTES.md)
2. [`docs/DEVELOPMENT_PLAN.ru.md`](docs/DEVELOPMENT_PLAN.ru.md)
3. [`docs/FULL_TECHNICAL_SPECIFICATION.ru.md`](docs/FULL_TECHNICAL_SPECIFICATION.ru.md)
4. [`docs/HOUSE_RULES.ru.md`](docs/HOUSE_RULES.ru.md)
5. [`../../docs/architecture/portfolio.md`](../../docs/architecture/portfolio.md)

## Focused checks (repo root)

```bash
node scripts/check-portfolio-registry.mjs
node scripts/check-registered-project-boundaries.mjs
node portfolio/preferans/tests/check-foundation.mjs
node scripts/check-no-raw-cyrillic.mjs
task repo:check
```

The raw Cyrillic check examines tracked files; stage newly added files before relying on its result. Run the entire `task ci` before PR review. No successful CI result is claimed by this README.

## Access

The route returns 404 if Portfolio Lab is disabled. When enabled, the shared project-grant check allows only granted users (Owner inherits access). The shell does not expose rooms, player data, cards, game APIs or secrets. Further controls and endpoints require additional backend protection and review.
