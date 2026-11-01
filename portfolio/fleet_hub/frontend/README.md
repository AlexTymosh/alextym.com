# Fleet Hub frontend (embedded Next.js module)

This directory owns the frontend implementation of Fleet VOR Hub.

- Entry point: `src/index.ts` exports `FleetHubApp`.
- Next.js host adapter: `frontend/app/fleet-vor-hub/page.tsx`.
- The three child routes under that host folder remain redirects.
- Public route and API paths remain `/fleet-vor-hub` and `/api/vor/*`.
- React, Next.js and TypeScript dependencies are installed ONCE under `frontend/`.
  `frontend/scripts/link-portfolio-deps.mjs` creates an ignored `node_modules`
  directory link inside `portfolio/fleet_hub/frontend/`, pointing to the host's
  `frontend/node_modules`. An existing repository-root `node_modules` is preserved.
- `frontend/next.config.mjs` sets the Turbopack root to the repo root.
- `frontend/tsconfig.json` exposes a single public import alias: `@fleet-hub`.
- Vercel project settings must allow source files outside the `frontend` Root Directory.
- `scripts/check-fleet-frontend-boundaries.mjs` validates ownership in CI.
- The project-owned vehicle and avatar images are in `src/`.

Do not import website components, website business services or other portfolio
projects here. Keep the main demo UI and internal panels under this directory.

The backend, SQLite seed and tests moved in PR #213; the Fleet backend became an installable local uv package in PR #214.

PR 4 introduces a no-global-CSS and import-boundary guard. See `../docs/css-boundary-audit.md`. Do not import standalone `.css`, use `:global` escapes, or import website implementation from Fleet. Host-owned baseline document styles are intentionally shared; route groups are not introduced in this PR.
