# Fleet VOR Hub — embedded portfolio demo

Fleet VOR Hub is an independently owned demonstration module inside the existing
Next.js website and FastAPI backend. It is not a separate deployed service.

## Current implementation

```text
frontend/app/fleet-vor-hub/                  Next.js route adapters / redirects
portfolio/fleet_hub/frontend/src/           Fleet UI and CSS Modules
portfolio/fleet_hub/frontend/src/index.ts   Public frontend entry
backend/app/main.py                         FastAPI host; mounts Fleet router and calls startup hook
portfolio/fleet_hub/backend/src/fleet_hub/
  router.py                                 Public Fleet API router
  api/                                      Fleet HTTP endpoints
  bootstrap.py                              Optional startup database preparation
  services/                                 Vehicle, operations, reporting and communication use cases
  persistence/sqlite.py                    SQLite connection lifecycle
  persistence/schema.py                    Schema readiness probes and interprocess bootstrap lock
  persistence/migrations.py                Legacy versioned SQLite migrations
portfolio/fleet_hub/tests/                  Fleet behavior and persistence regressions
backend/tests/test_fleet_startup.py         Host/Fleet lifespan integration tests
```

The frontend host imports Fleet through the public `@fleet-hub` entry;
FastAPI mounts `fleet_hub.router`. Do not reintroduce Fleet implementation
inside the website's `frontend/` or `backend/app/` modules.

## Stable public contracts

- Demo page: `/fleet-vor-hub`.
- Fleet HTTP API: `/api/vor/*`.
- Legacy redirects: `/fleet-vor-hub/register`, `/fleet-vor-hub/new-defect`,
  `/fleet-vor-hub/process` redirect to `/fleet-vor-hub`.
- Keep authentication, cookies, Origin handling, API behavior and existing
  website Chat/RAG/SSE behavior unchanged during persistence refactors.

## SQLite lifecycle and data safety

- The packaged demo seed remains immutable. Approved SHA-256:
  `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`.
- Runtime SQLite lives outside the packaged seed; its path is chosen by
  `fleet_hub.services.vor_store.database_path()` and can be overridden with
  `VOR_DEMO_DB_PATH`. Never reset a live runtime database as part of a migration.
- The host invokes `fleet_hub.bootstrap.prepare_demo_database()` in FastAPI's
  lifespan when `VOR_DEMO_ENABLED=true`. An optional Fleet bootstrap failure is
  logged without taking down the website. Standalone Fleet users and tests retain
  lazy, guarded database preparation.
- First-time seed publication is atomic. Per-database cross-process locks protect
  schema initialization, while ready v1 databases avoid the lock on the normal
  connection path. v2 schema and operations readiness are checked on demand.
- Legacy v1/v1.1/v1.2 migration versions preserve their existing successful
  commit boundaries; on failure, pending writes are rolled back and the original
  `PRAGMA foreign_keys` setting is restored. Do not claim the *whole* upgrade
  across all versions is one atomic transaction.
- Regression tests use disposable SQLite files (`tmp_path`) and verify
  concurrent bootstrap, recovery, data preservation, and foreign-key integrity.

## Auth and email delivery

- `fleet_hub.api.dependencies` owns FastAPI session and Origin checks;
  sibling routers no longer import shared guards from `api.vor`.
- `fleet_hub.services.message_delivery` owns email validation, server-derived
  recipients, allowlists, quotas, provider dispatch and error categories.
  The API adapter maps those categories to the existing HTTP status codes.
- Live email clients can supply `request_id`; keyed attempts are claimed
  in an additive SQLite journal, then dispatched with a Resend
  `Idempotency-Key`. Replaying a successful request with the same payload
  reuses its stored response without charging quota or resending.
- Pending or uncertain keyed attempts return a conflict rather than retry
  automatically. The local journal is durable, but provider acceptance,
  event persistence, and journal completion are not atomic together.
  Manual reconciliation is needed for indeterminate attempts.
- Existing callers that omit `request_id` remain supported but do not
  receive the durable deduplication guarantee. The browser-held request
  key is not currently preserved across a full page reload.
- Relevant regression tests: `test_vor_api_dependencies.py`,
  `test_vor_message_delivery.py`, `test_vor_email_idempotency.py`.

## Verification and ownership

Use `task ci` from the repository root and the tests under
`portfolio/fleet_hub/tests/` and `backend/tests/test_fleet_startup.py`.
The last full CI result must be verified in the relevant branch and is not
asserted by this documentation alone. See `docs/architecture/portfolio.md`
for module ownership and `SESSION_NOTES.md` for the current work checkpoint.

Deployment is shared with the host: Vercel for Next.js and Render for FastAPI.
No independent Fleet service or database infrastructure is required.
