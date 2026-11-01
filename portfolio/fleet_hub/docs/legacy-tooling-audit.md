# Fleet VOR Hub — post-migration tooling audit (PR 5)

**Baseline:** `main` at `12cfca4fe8ec4c95794db54c5e52848dcecbf56b` (PR #215 merged, 2026-11-01).

## Retired, one-time scripts (19)

These installers and their old shape checks targeted v1/v2 source layouts under
`frontend/app/fleet-vor-hub/` and `backend/app/{api,services}/`. The active
implementation now lives under `portfolio/fleet_hub/` and the website imports
its public adapters. Running an old installer against the current tree could
recreate incompatible code paths or undo the migration.

- `scripts/apply_vor_pr02.py`
- `scripts/apply_vor_pr03.py`
- `scripts/apply_vor_pr0405.py`
- `scripts/apply_vor_pr06.py`
- `scripts/apply_vor_pr06_ui_polish.py`
- `scripts/apply_vor_pr07.py`
- `scripts/apply_vor_pr11_ts_hotfix.py`
- `scripts/apply_vor_ui_shell.py`
- `scripts/apply_vor_ui_workflow.py`
- `scripts/check_vor_pr0405.py`
- `scripts/check_vor_pr06.py`
- `scripts/check_vor_pr06_ui_polish.py`
- `scripts/check_vor_pr07.py`
- `scripts/check_vor_pr11_ts_hotfix.py`
- `scripts/check_vor_ui_refinement.py`
- `scripts/check_vor_ui_shell.py`
- `scripts/check_vor_ui_workflow.py`
- `scripts/install_vor_hub.py`
- `scripts/repair_vor_ui_entry.py`

PR 5 removes these files **after** installer preflight verifies that the
actual working tree is clean, the checked baseline commit is current, and
none of the deleted scripts is referenced by active build/deployment
configuration. They remain recoverable from the Git history (PRs #198–#215).
This is an explicit hygiene change: no active app, package, data or API file
is moved, and no runtime database is opened by the installer.

## Kept operational / developer utilities

- `scripts/start-vor-backend.ps1` and `scripts/start-vor-frontend.ps1` — local dev launchers.
- `scripts/backup_vor_v2.py` — manual SQLite online backup (retain; do not invoke in CI).
- `scripts/configure-vor-subscribers.ps1` — manual demo setup.
- `scripts/frontend-dev.ps1`, `scripts/stop-dev.ps1`, `scripts/smoke.ps1` — host tooling.
- `scripts/telegram-*` — outside Fleet migration scope.
- `scripts/check-portfolio-foundation.mjs`, `check-fleet-frontend-boundaries.mjs`,
  `check-website-portfolio-boundaries.mjs`, `check-fleet-backend-boundaries.mjs`,
  and `check-fleet-legacy-tooling.mjs` — active read-only CI boundary guards.

## Validation and limitations

- GitHub code search returned no references to three representative legacy tools.
  That alone is not exhaustive evidence; installation also scans active CI,
  runtime and deployment configurations for **all** retirement candidates.
- Static CI verifies no obsolete script is left and expected live utilities
  remain. It cannot detect a user's external personal scripts or local aliases.
- The browser tests use **mocked authenticated API responses** to verify UI
  transitions and sign-out. They do not establish production authentication
  security; FastAPI TestClient tests separately verify real login/logout,
  cookie-gated bootstrap and disposable SQLite operations.
- Production Vercel/Render smoke remains a manual post-merge gate; see
  `deployment-smoke.md`. Do not claim a production deployment based on CI alone.
