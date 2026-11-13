# Workforce & Recruitment Intelligence — embedded portfolio module

**Status:** foundation only; **all browser and API routes deliberately return HTTP 404** until project-grant authorization is implemented and tested in the next commit. Do not grant access or release a live demonstration at this stage.

This module belongs to `portfolio/workforce_intelligence/`. Its host-owned adapters are:

- Catalogue: `/portfolio` (not published, HTTP 404 in this increment)
- Application: `/portfolio/workforce-intelligence` (HTTP 404)
- API namespace: `/api/workforce/*` (only a denied `/status` probe currently exists)

The canonical English specification is
[`docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md`](../../docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md).
Execution history and subsequent commit plan live in [`SESSION_NOTES.md`](SESSION_NOTES.md).

## Ownership contract

- Website Next.js and FastAPI import only each project's **public** entry points.
- All Workforce UI and scoped styles live under `frontend/src`; all future Workforce domain services and persistence belong to its backend package.
- Never import Fleet Hub implementation, share its SQLite DB, or copy its authentication dependency.
- Shared Firebase identity exists, but **identity admission is not a project grant**. The shared Portfolio Lab control plane must enforce the explicit Workforce grant at the Next.js route/BFF and FastAPI (including direct Render access) before routes become available.
- Even if `WORKFORCE_INTELLIGENCE_ENABLED=true` is set accidentally, both adapters remain closed until the authorized integration is explicitly implemented.
- The global Owner role and credential provisioning remain independent of Workforce domain roles. All accepted members will have one effective Workforce permission level.

## Build integration

- Frontend is imported through `@workforce-intelligence` and uses the existing host React/Next dependency installation.
- Backend is an editable local path dependency of `backend/pyproject.toml`, installed into the existing FastAPI runtime and copied by the shared Dockerfile.
- Project manifests are validated by existing registry and generic frontend/backend import-boundary checks.
- The separate Workforce SQLite lifecycle, migrations and seed are **not implemented in Commit 01**.

## First-commit verification

From repository root:

```powershell
node scripts/check-portfolio-registry.mjs
node scripts/check-registered-project-boundaries.mjs
node scripts/check-workforce-scaffold.mjs
uv sync --project backend --frozen --extra dev
task ci
```

Expected: `/portfolio`, `/portfolio/workforce-intelligence`, and `/api/workforce/status` are **404** while this commit is deployed. This is intentional, not a successful authenticated user-flow test. Authentication and all authorisation tests are scheduled for Commit 02.
