# Fleet Hub backend (planned destination)

This directory is intentionally documentation-only in PR 1.

The backend migration will move Fleet-specific `vor_*` API modules, services and **the existing SQLite seed** to `portfolio/fleet_hub/backend/`. A single public router entry will register the exact same `/api/vor/*` paths in the site FastAPI app.

The host Dockerfile currently copies only `backend/app` and not the root `portfolio/` directory. Adapt Docker build context, package installation and uv dependency wiring in the backend migration PR. No separate Render service is planned.

The seed must retain its exact SHA-256, and `VOR_DEMO_DB_PATH` must continue to work with current configuration. Keep read/write runtime SQLite separate from the immutable seed. Verify fresh starts, restarts, exports, authentication and all existing API contracts.
