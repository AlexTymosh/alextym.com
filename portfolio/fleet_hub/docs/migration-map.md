# Final migration inventory update (PR 5, 2026-11-01)

PRs #208, #209, #213, #214 and #215 are merged. The active Fleet frontend, backend and SQLite seed belong to `portfolio/fleet_hub/`; host adapters remain under `frontend/app/fleet-vor-hub/` and `backend/app/`. A local uv package supplies the backend project. PR 5 removes 19 obsolete one-time migration/check scripts, adds authenticated-state browser regression and records production validation as a manual post-merge step. See `legacy-tooling-audit.md` and `deployment-smoke.md`.

**All earlier paths and warnings in the historical snapshot below are archival, not instructions to re-apply old patches.**

---

PR 3 backend implementation update (2026-10-29): the eight API routers, eight
services, unchanged approved SQLite seed and 16 test files have moved under
`portfolio/fleet_hub/`. `backend/app/main.py` mounts one Fleet router; tiny
`app.api.vor*` and `app.services.vor*` aliases preserve legacy imports.
The inventory below is the baseline and remains useful for auditing.

# Fleet VOR Hub — source ownership and migration map

PR 2 implementation update (2026-10-27): frontend components, CSS and bundled
images have moved into `portfolio/fleet_hub/frontend/src/`. The four
Next.js route files remain in the website host. The original inventory
below is retained as a pre-migration audit record.

Snapshot of `main` reviewed on 2026-10-26, after PR #207 merged. This is a **planning inventory**, not proof that code has already moved. Re-run a file-tree audit before each move.

## Frontend: 29 source and asset files

All currently under `frontend/app/fleet-vor-hub/`. Move project implementation under `portfolio/fleet_hub/frontend/src/`; retain only Next.js route wrappers at the old location.

### Host adapters to retain

- `page.tsx` -> existing demo URL `/fleet-vor-hub`
- `register/page.tsx` -> redirect
- `new-defect/page.tsx` -> redirect
- `process/page.tsx` -> redirect

### Project-owned code to move

- `FleetApp.tsx`, `VorHub.tsx`, `fleet-app.module.css`, `vor.module.css`
- `issue-hub-redesign.css` (audit global selectors and imports)
- `calendar/CalendarBoard.tsx`, `calendar/calendar-board.module.css`
- `dashboard/DashboardPanel.tsx`, `dashboard/dashboard.module.css`
- `message-card/MessageCard.tsx`, `message-card/message-card.module.css`
- `new-defect/Panel.tsx`, `new-defect/new-defect.module.css`
- `operations/AssetSignals.tsx`, `OperationsPanel.tsx`, `OperationsQueuePanel.tsx`, `WorkflowLibraryPanel.tsx`, `WorkflowSettingsPanel.tsx`, their CSS Modules, `workflow-redesign.css` (global selector audit)
- `process/Panel.tsx`, `process/process.module.css`
- `reconciliation/Panel.tsx`, `reconciliation/reconciliation.module.css`
- `register/Panel.tsx`, `register/register.module.css`
- `vehicle-photo/VehiclePhoto.tsx`, `vehicle-photo/vehicle-photo.module.css`, `vehicle-photo/assets/fleet-van-demo.webp`

The full source of truth is the Git tree, not this compressed list. Site-specific asset reference to audit: `/images/profile/alex.webp` in `FleetApp.tsx`.

## Backend: eight API modules and eight service-related items, including seed

Currently:

```text
backend/app/api/
  vor.py
  vor_checklist.py
  vor_data.py
  vor_intake.py
  vor_operations.py
  vor_reconciliation.py
  vor_reporting.py
  vor_workflow_admin.py

backend/app/services/
  vor_data.py
  vor_exports.py
  vor_intake.py
  vor_operations.py
  vor_reconciliation.py
  vor_reporting.py
  vor_store.py
  vor_workflow_admin.py
  vor_seed.sqlite3
```

That is eight router files plus **nine** service/seed files (17 total). `backend/app/main.py` registers these eight routers directly; replace with one application-module registration, preserving all generated routes, methods, response shapes and authentication behavior.

### Known high-risk references

- `vor_store.py`: `SEED_FILE = Path(__file__).with_name("vor_seed.sqlite3")` and default `LOCAL_FILE` derived from `__file__`. Define a stable runtime path before moving this file; do not allow a silent seed reset.
- `vor_reconciliation.py` imports the existing Excel serializer `vor_exports._sheet`.
- API files import `required` and `same_origin` from the current `vor.py`; preserve same-origin protections and session behavior.
- `backend/Dockerfile` copies only `backend/app` as Python application code.
- `backend/pyproject.toml`, `backend/uv.lock` and Python package discovery need updating after source moves.
- `backend/tests/test_vor_seed_contract.py` currently resolves the seed through a relative parent path.
- `VOR_DEMO_DB_PATH` selects runtime storage; never repurpose it as the seed path.

## Existing backend tests to preserve

- `test_vor_checklist.py`
- `test_vor_contact_management.py`
- `test_vor_data_api_errors.py`
- `test_vor_data_foundation.py`
- `test_vor_demo.py`
- `test_vor_email_validation.py`
- `test_vor_intake.py`
- `test_vor_operations.py`
- `test_vor_reconciliation.py`
- `test_vor_reporting.py`
- `test_vor_seed_contract.py`
- `test_vor_seed_exports.py`
- `test_vor_subscribers.py`
- `test_vor_wildcard_regression.py`
- `test_vor_workflow_admin.py`
- `test_vor_workflow_owners.py`

## Legacy integration scripts

The repository also contains many `scripts/apply_vor_*`, `scripts/check_vor_*`, `scripts/install_vor_hub.py`, `scripts/backup_vor_v2.py`, `scripts/start-vor-*.ps1`, and `scripts/configure-vor-subscribers.ps1`.

Classify each as (A) reusable project tooling, (B) obsolete one-time patch tooling, or (C) host-specific tooling. Only after verifying consumers should (A) move into `portfolio/fleet_hub/scripts/` and (B) be removed. Do not sweep-delete in PR 1.

## CSS / layout boundary issues

- `frontend/app/layout.tsx` currently wraps all routes with site navigation and footer.
- `frontend/app/globals.css` applies host-global HTML/body/button/input and site classes.
- Fleet contains regular CSS files with selectors like `.root`, `.page`, `.hero` in addition to CSS Modules. Audit exactly where they are imported; scope all project CSS under a project-specific root, or convert to modules as appropriate.
- `frontend/next.config.mjs` has `turbopack.root` pointing to the `frontend/` directory. Future imports from `portfolio/` require deliberate build configuration.
- Vercel's project Root Directory is frontend-scoped; configure inclusion of sources outside that directory when moving code.

## Unchanged public contract (all migration PRs)

- `/fleet-vor-hub` remains active.
- `/fleet-vor-hub/register`, `/fleet-vor-hub/new-defect`, `/fleet-vor-hub/process` retain redirects.
- `/api/vor/*` endpoints and cookies retain paths and semantics.
- `/fleet-vor-hub-01` and `/api/vor-01` remain retired.
- Home, Chat, Contact, Resume, unrelated case studies, RAG and Telegram are behaviorally unchanged.
- No `/portfolio` page or menu item is launched in these migration PRs.
