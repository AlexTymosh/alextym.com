# Fleet VOR Hub — v1.1 UI & workflow update

**Branch:** `feat/fleet-vor-hub-demo` (keep the existing branch)

**Install scope:** Incremental patch for the already working v1 Fleet VOR Hub on `alextym.com`. No new dependencies, no changes to original portfolio features, no reset of SQLite.

## Changes

1. **Maintenance & Compliance** with MOT / Inspection / Service dates + booking actions is in the wide, highlighted `SELECTED VEHICLE · FLEET CASE` top panel. Removed the redundant standalone maintenance panel.
2. Lower middle area: a **vertical, numbered workflow** on the left and **Next action** card on the right. Workflow includes completed/current/pending visual stages. On small screens the blocks stack so nothing is hidden.
3. Scenario selector uses the 13 existing SQLite `workflow_templates`: engine, AdBlue, door, electrical, tyre, gearbox, fuel, brakes, MOT, service, inspection, glass, cooling. Selection applies to the current **open ticket** and persists changes via `POST /api/vor/scenario`. The user confirms reset of that ticket's completed stage progress. Ticket ID and old activity history are preserved, while the issue/title and next action update.
4. `Vehicle Chatter` renamed to **Communication history** with subtitle `All sources` (natural English UI).
5. Responsible is selected from five demo staff (`Alex Tym`, `Victoria B.`, `Jason W.`, `Janine M.`, `Gosha T.`). One-time SQLite migration assigns them across the 20 vehicles. Afterwards the name can be changed in top vehicle panel; API persistence and history log included. Existing notes/bookings/subscriptions remain intact.

**Scope note:** Choosing a scenario is a demo workflow change, not a real integration with KEY2/HOTH; availability/VOR status is intentionally not automatically changed when switching an engine scenario to MOT etc. These are separate business concepts.

## Install (Windows PowerShell)

1. Stop the two running terminals with `Ctrl+C`.
2. Make sure you are already on `feat/fleet-vor-hub-demo` and that your local edits are committed/stashed. Optionally back up `backend/_local/vor_hub.sqlite3`.
3. Extract this ZIP **into the repository root**, allowing files to overwrite those with the same paths. Do not copy the ZIP's containing folder into the repo.
4. Start the existing scripts in **two terminals** from the repo root:

```powershell
.\scripts\start-vor-backend.ps1
```

```powershell
.\scripts\start-vor-frontend.ps1
```

5. Visit `http://localhost:3000/fleet-vor-hub` and hard refresh (`Ctrl+F5`). Password stays unchanged (`VOR_DEMO_PASSWORD`, default `Victoria` from the launcher).

No need to rerun `scripts/install_vor_hub.py` — the router is already registered from v1.

## Acceptance checklist

- [ ] Upper vehicle case card shows MOT / Inspection / Service with `Book / view`.
- [ ] Middle area shows vertical numbered stages **left**, `Next action` **right** at desktop width.
- [ ] Select engine → tyre, confirm; six tyre-specific stages appear and start at stage one.
- [ ] Refresh; selected scenario persists. Prior internal notes remain.
- [ ] Complete a stage; current stage and next action advance.
- [ ] Change `Responsible` to `Jason W.`; refresh and confirm persistence.
- [ ] Chatter header is `Communication history` / `All sources`.
- [ ] Dashboard, Excel, calendar and appointment booking still work.

## Verifications performed during package preparation

- Python FastAPI+SQLite API regression suite: **4 passed** (`test_vor_demo.py`, `test_vor_v1_update.py`, `test_vor_v1_1.py`).
- TypeScript TSX syntax transpilation: no diagnostics.
- Full Next.js browser rendering, npm build and E2E not run in the isolated packaging environment; verify locally.

## Files overwritten

```
frontend/app/fleet-vor-hub/VorHub.tsx
frontend/app/fleet-vor-hub/vor.module.css
backend/app/api/vor.py
backend/app/services/vor_store.py
backend/tests/test_vor_v1_update.py
backend/tests/test_vor_v1_1.py
SESSION_NOTES.md
RUN_VOR_HUB.md
```

The ZIP does **not** include the persisted local database, provider credentials, any unrelated files, or an updated seed. Production deployment requires separate persistence planning; this package targets local demo only.
