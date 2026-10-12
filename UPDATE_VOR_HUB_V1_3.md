# Fleet VOR Hub v1.3 — patch over v1.2

## Apply locally (Windows 11, PowerShell, PyCharm)

1. Work in existing branch `feat/fleet-vor-hub-demo`. In project root run `git status --short`; commit/stash changes before overwriting.
2. Stop both processes with `Ctrl+C`. If you want a backup, copy `backend/_local/vor_hub.sqlite3` somewhere safe.
3. Extract `fleet_vor_hub_v1_3_patch.zip` **into repository root**; merge `frontend/`, `backend/` and docs; replace same-named files. Do **not** unzip as `alextym/fleet_vor_hub_v1_3_patch/...`.
4. Restart (from project root, two PowerShell terminals):

```powershell
.\scripts\start-vor-backend.ps1
```

```powershell
.\scripts\start-vor-frontend.ps1
```

5. Open `http://localhost:3000/fleet-vor-hub` → `Ctrl+F5`; sign in with configured demo password (default in local launcher: `Victoria`).
6. Open `Manage` next to subscribers, press `Edit` on Alex Tym / Victoria B. (or `Add email contact`), enter an actual test address, save. New contact automatically subscribes to **current selected vehicle**; old contacts can be checked/unchecked per vehicle.
7. Change scenario, navigate Vehicles/Dashboard/Calendar; verify condensed horizontal workflow and subdued history panel. Select `External email`: recipients are from subscription chips; Subject stays editable. With real mode disabled, submit will only simulate and log.

**Important:** no `configure-vor-subscribers.ps1` invocation is necessary. The legacy helper can remain unused; `Manage` takes precedence. The live SQLite file is not modified at installation time and persists when a server first starts with the new code.

## Real email deployment

Frontend is already set up to call `/api/vor/*` through the Next.js rewrite. Resend calls run **only on FastAPI**.

On your **backend provider** (Render or other host), configure:

| Variable | Example / meaning |
| --- | --- |
| `VOR_DEMO_ENABLED` | `true` |
| `VOR_DEMO_PASSWORD` | demo access password; use a non-obvious value on public deployment |
| `VOR_DEMO_SEND_REAL_EMAIL` | `true` (explicit opt in) |
| `VOR_DEMO_EMAIL_LIMIT` | `15` (recipient slots per day, capped at 30) |
| `RESEND_API_KEY` | existing server-side Resend key or new key with domain access |
| `VOR_DEMO_FROM_EMAIL` | sender on verified domain; **may omit** when existing `CONTACT_FROM_EMAIL` is verified |
| `VOR_DEMO_PUBLIC_URL` | `https://alextym.com/fleet-vor-hub` (update if canonical domain differs) |
| `VOR_DEMO_ALLOWED_ORIGINS` | `https://alextym.com,https://www.alextym.com` (plus any production Vercel preview domains you intentionally use) |
| `VOR_DEMO_ALLOWED_EMAIL_DOMAINS` | `scas.nhs.uk` (add external partner domains only if approved for the demo) |
| `VOR_DEMO_ALLOWED_RECIPIENTS` | optional comma-separated *exact-address* exceptions; not needed for addresses on permitted domains |
| `VOR_DEMO_DB_PATH` | persistent DB path, e.g. `/var/data/vor_hub.sqlite3` on mounted Render persistent disk |

No frontend variable contains email keys. The literal email recipients are entered through **Manage**, not the hosting environment. The backend refuses real sending when neither domain policy nor exact-address policy is configured. Placeholder `.example` contacts are intentionally refused in live mode until unsubscribed or edited.

In Resend dashboard verify the sending domain and authenticate it (SPF/DKIM) before testing. First send to **one address you control**; limit and Bcc prevent accidental broad disclosure. This feature sends a notification referring to the vehicle and ticket; it does not forward real operational content.

### SQLite deployment persistence

Render Free file storage is ephemeral, lost on service idle/redeploy. Even with the route functional, edits via `Manage` will disappear when the service restarts. This patch does not add an external datastore. For durable use, move backend service to a paid Render plan with a persistent disk mounted at `/var/data`, set `VOR_DEMO_DB_PATH` accordingly, or plan a later managed PostgreSQL migration. Do not rely on a git-committed SQLite file as production storage.

### Real send diagnostic steps

- `403 A subscribed address is outside permitted recipient domains`: uncheck a demo external subscriber or update an allowed domain policy.
- `503 Live sending requires...`: verify sender/Resend key/public URL, and at least one allowed domain/recipient.
- `429 Daily recipient limit...`: daily quota is exhausted (counts recipients, not messages).
- `502 Email provider unavailable`: check Render application logs, Resend dashboard, verified sender/domain and provider limits.
- `401 Password required`: re-login; both browser and backend must be on the same rewrite path.

## Code changes

- `frontend/app/fleet-vor-hub/VorHub.tsx`: compact combined workflow/action; horizontal stage grid; Manage add/edit/subscribe UI; no `Vehicle timeline` line.
- `frontend/app/fleet-vor-hub/vor.module.css`: updated layout, dashed messaging panel, gray timeline, Manage form styling.
- `backend/app/api/vor.py`: authenticated contact edit route; trusted-domain recipient policy in addition to exact allowlist; sender fallback and quota reservation.
- `backend/app/services/vor_store.py`: persist edited contacts (legacy env sync no longer authoritative), update contacts, atomically reserve recipient quota.
- `backend/tests/test_vor_v1_3.py`: Manage, domain-based live delivery and negative cases.
- `backend/tests/test_vor_v1_update.py`: refresh outdated migration-count test to account for v1/v1.1/v1.2 migrations.
- `SESSION_NOTES.md`: current architecture and next steps for an AI agent.

## Checks

Backend suite: 9 tests passed, no actual mail sent. TSX transpilation has no syntax diagnostics. Full Next.js build/browser verification remains to be performed in the local repository with dependencies installed.
