# Fleet VOR Hub v1.2 — UI + subscriber email + overdue compliance patch

Branch: `feat/fleet-vor-hub-demo`. Apply **after v1.1**.

## Installation

1. From PowerShell in project root: `git status --short` and optionally commit/stash unrelated edits.
2. Stop local backend/frontend (Ctrl+C).
3. Back up `backend/_local/vor_hub.sqlite3` if you want a rollback point.
4. Extract this ZIP **into the root folder**, keeping `frontend/`, `backend/`, `scripts/` paths.
5. Restart `./scripts/start-vor-backend.ps1` and `./scripts/start-vor-frontend.ps1` (Windows: `.\scripts\...`).
6. Open `http://localhost:3000/fleet-vor-hub`, sign in and refresh (Ctrl+F5).

## Changes

- Desktop: `Vehicles | [Selected vehicle / Workflow+Action / Communication history]`.
  The workflow and next-action row no longer fills the entire page height; Chatter is below and starts directly beside the vehicle list.
- Email: composer shows all subscribers read-only, preserves Subject, saves original draft as a Chatter message, and (if explicitly configured) sends a standard test notification **to all allowlisted subscribers** with a protected page link.
- Contacts: four seeded contacts, including two employee email addresses configured via environment on every car; one fictional external partner per car.
- Compliance: 12 deterministic synthetic due dates become overdue; overdue cards are muted red. Calendar's unbooked list includes overdue maintenance.

## Real mail is OFF by default

The demonstration displays a simulated outgoing notification until `VOR_DEMO_SEND_REAL_EMAIL=true`. All subscribers must be explicitly approved via `VOR_DEMO_ALLOWED_RECIPIENTS` or the API refuses real sends. Before live tests, remove the fictional external subscriber from the selected vehicle via `Manage`. Set `VOR_DEMO_PUBLIC_URL` to a reachable HTTPS page so the email link works for recipients. A live mail provider must be configured separately. Sending is never triggered merely by loading the page or switching tabs.

## Tests

Tests: `backend/tests/test_vor_v1_2.py` and amended `test_vor_v1_1.py`. The new tests use mocked mail and no real recipients are contacted. Verify Next.js typecheck and browser layout locally.

## Rollback

Restore the previous frontend/backend code from your commit. Restore the backed-up SQLite database if you also want to undo the one-off contact and synthetic due-date migration. Do not delete the database simply to roll back the layout.

### Configure the two internal email addresses

To keep internal organisational email addresses out of public GitHub, set these two keys in
**ignored** `backend/.env` before or after first startup:

```dotenv
VOR_DEMO_ALEX_EMAIL=YOUR-ALEX-EMAIL
VOR_DEMO_VICTORIA_EMAIL=YOUR-VICTORIA-EMAIL
```

Values are read into SQLite; changing them and restarting backend updates the two contacts without losing subscriptions. If unset, the two internal entries stay on demonstration `@fleet-demo.example` addresses. For real mail, also include the same addresses in `VOR_DEMO_ALLOWED_RECIPIENTS`.

Instead of manual editing, you can execute the included `scripts/configure-vor-subscribers.ps1` with
`-AlexEmail` and `-VictoriaEmail` arguments. It merges only these two variables into the existing
ignored `backend/.env` file and does not replace unrelated settings.
