# Fleet Hub backend (embedded project, PR 3)

Source: `backend/src/fleet_hub/`, loaded by the shared FastAPI host (`backend/app`).
There is exactly one public router, `fleet_hub.router.router`, registered with
`prefix="/api"`; internal routers preserve all existing `/api/vor/*` paths.
The host retains transitional `app.api.vor*` and `app.services.vor*` import
aliases for legacy scripts; they contain no Fleet business logic.

The existing `backend/uv.lock` is unchanged. The host `backend/app/__init__.py`
registers this embedded source tree on Python's import path. The Dockerfile
copies it to `/portfolio/fleet_hub/backend/src` to maintain the same relative
layout to host `/app/app`. No independent server, uv workspace, or package
publication is introduced. This explicit bridge can be replaced by a proper
editable path dependency in a separately tested packaging-only PR.

`services/vor_seed.sqlite3` is immutable and byte-identical to the approved
v2 seed (SHA-256 `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`).
Runtime state is a separate SQLite file. `VOR_DEMO_DB_PATH` always takes
priority; the previous `backend/_local/vor_hub.sqlite3` Windows default and
`/app/_local/vor_hub.sqlite3` Docker default are preserved.

Never overwrite an existing runtime DB or alter the email allowlist, sessions,
authentication, CSRF protection, or public API contract while migrating.
