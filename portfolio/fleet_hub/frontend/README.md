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

The backend and SQLite have NOT moved in PR 2. That is the dedicated PR 3.
