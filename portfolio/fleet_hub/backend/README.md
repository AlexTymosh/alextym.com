# Fleet Hub backend — embedded Python package (PR 3.1)

The project owns `backend/src/fleet_hub/`, exposing `fleet_hub.router.router` as
its one public FastAPI router. The shared website backend registers that router
once, with `prefix="/api"`; all existing `/api/vor/*` methods and semantics
remain unchanged. Legacy `app.api.vor*` and `app.services.vor*` adapters remain
for compatibility with older scripts and tests.

## Installation and deployment

`backend/pyproject.toml` declares `alextym-fleet-hub==0.1.0` and maps it to the
local editable path `../portfolio/fleet_hub/backend` through `[tool.uv.sources]`.
The project package is declared in this directory's `pyproject.toml`, with the
`src/` layout and SQLite seed explicitly included as package data.

From repository root:

```powershell
cd backend
uv lock
uv sync --extra dev
uv run python -m pytest
cd ..
task ci
task docker:build
```

Commit the regenerated `backend/uv.lock` together with the manifest changes.
In Docker, host `pyproject.toml` lives at `/app/` and this package at
`/portfolio/fleet_hub/backend/`. The relative path mapping therefore works
without an extra service or a manually altered `sys.path`.

## Data contracts

- The immutable v2 SQLite seed is `src/fleet_hub/services/vor_seed.sqlite3`.
- Approved SHA-256: `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`.
- The runtime SQLite database remains separate: `backend/_local/vor_hub.sqlite3`
  locally or `/app/_local/vor_hub.sqlite3` in the existing Docker image.
- `VOR_DEMO_DB_PATH` remains the authoritative runtime override.
- Do not overwrite production runtime databases or relax the existing auth,
  session, same-origin, email-recipient allowlist, or other security contracts.

PR 3.1 changes packaging and test discovery only. It does NOT change the seed,
API implementation, routes, migrations, UI, or deployment service topology.
