# SESSION_NOTES.md — Fleet VOR Hub demo · v1.3.1

**Branch:** `feat/fleet-vor-hub-demo`  
**Target project:** https://github.com/AlexTymosh/alextym.com (`frontend`: Next.js 16; `backend`: FastAPI)  
**Integration:** isolated route `/fleet-vor-hub`, not in public site navigation. API `/api/vor/*` through Next.js backend rewrite.  
**Last change:** 12 October 2026. **Status:** patch prepared and automated backend tests run; not deployed by the assistant.  

## Goal

Show managers a compact, vehicle-centred VOR case management demo: vehicle status, linked PS000xxx tickets, multiple workflow templates, next actions, communication history, maintenance scheduling, dashboard. Synthetic vehicles, workshops, tickets and KEY2/HOTH events; integrations with those systems are **simulated**, not live.

## Architecture & storage

- `frontend/app/fleet-vor-hub/VorHub.tsx`, `vor.module.css`: client-side demo UI, fixed overlay, independent theme.
- `backend/app/api/vor.py`: password-protected route (signed HTTP-only cookie), contacts, subscriptions, events, workflow, bookings, Excel and ICS exports, optional Resend delivery.
- `backend/app/services/vor_store.py`: `sqlite3` state and seed/migrations. `backend/app/services/vor_seed.sqlite3` contains 20 fictional vehicles, 40 synthetic PS tickets, scenarios and sample activity.
- Live contacts, subscriptions, events and bookings persist in SQLite at `VOR_DEMO_DB_PATH`, default `backend/_local/vor_hub.sqlite3`. This DB is ignored by Git. Never delete it during patches.
- `backend/app/main.py` router already registered in previously installed Fleet Hub. The v1.3 archive does **not** change this entrypoint.
- Existing site's `RESEND_API_KEY` and optionally `CONTACT_FROM_EMAIL` may be reused. Resend must be configured with a verified sending domain.

## Current UX (v1.3)

- Vehicles: separated cards, each shows Workshop.
- Selected Vehicle: broad top panel with Maintenance & Compliance dates; red-tinted overdue items.
- Workflow + Next Action: **one short panel**, horizontal left-to-right stages (2 rows if necessary), scenario picker and Complete stage; next-action summary alongside.
- Communication history: muted-grey timeline and dashed border, no redundant `Vehicle timeline` subtitle.
- Subscriber `Manage`: add contact by name/email/role and subscribe immediately; edit an existing contact (e.g. replace Alex/Victoria placeholder addresses), select/unselect subscribers per vehicle. **No special CLI or per-address env setup**.
- External Email: `Subject` + text; no manual To; backend chooses **all current subscribers**. Default is simulation. Live Resend sends a **notification with vehicle, ticket and link**, not the internal message text. `To/Bcc` avoids exposing the entire list of subscriber emails to other recipients.
- Calendar: MOT/Inspection/Service bookings with garage and dates, list of missing bookings in next 60 days, ICS export. Dashboard with synthetic metrics and Excel export.
- Source of truth for contact email addresses is now the UI/database: legacy `VOR_DEMO_ALEX_EMAIL`, `VOR_DEMO_VICTORIA_EMAIL` are not re-synced after migration.

## Deployment requirements (important)

Set the following in the **backend** hosting environment (e.g. Render), not `NEXT_PUBLIC_*`:

```
VOR_DEMO_ENABLED=true
VOR_DEMO_PASSWORD=<chosen password>
VOR_DEMO_SEND_REAL_EMAIL=true
VOR_DEMO_EMAIL_LIMIT=15
VOR_DEMO_PUBLIC_URL=https://alextym.com/fleet-vor-hub
VOR_DEMO_ALLOWED_ORIGINS=https://alextym.com,https://www.alextym.com
VOR_DEMO_ALLOWED_EMAIL_DOMAINS=scas.nhs.uk
RESEND_API_KEY=<existing verified Resend key>
VOR_DEMO_FROM_EMAIL=<verified demo sender; optional if CONTACT_FROM_EMAIL is configured>
VOR_DEMO_DB_PATH=/var/data/vor_hub.sqlite3
```

By default, only named *domains* or exact `VOR_DEMO_ALLOWED_RECIPIENTS` may receive mail. v1.3.1 also accepts the explicit wildcard `VOR_DEMO_ALLOWED_EMAIL_DOMAINS=*`, which allows all domains for subscribers added through `Manage`. This must not be used with a weak public demo password: the 15-recipient/day quota is only a secondary safeguard. Unapproved subscribers block the **whole** delivery when the wildcard is not enabled. Real sending requires login, explicit enablement, daily recipient quota and valid sender. Password `Victoria` remains supported locally; change it before enabling live sending publicly.

**Persistent deployment data:** Render Free has ephemeral storage and no persistent disk, including restart after idling. If using Render Free, entered emails and saved history will be lost on restart. For durable deployed Manage/history, use a paid Render service with persistent disk mounted at `/var/data` and `VOR_DEMO_DB_PATH` as above, or migrate to a managed durable database (not implemented in this patch). **Do not claim persistence on Render Free.** See `UPDATE_VOR_HUB_V1_3.md`.

## Operations / UI testing

- Backend: open `http://127.0.0.1:8000/api/vor/session`; frontend `http://localhost:3000/fleet-vor-hub`.
- Open `Manage`: edit Alex Tym and Victoria B. emails from `.example` to chosen addresses, uncheck external fake subscribers, optionally add more by name and email.
- Real send is off until explicitly enabled and provider configured on backend. A failed Resend request returns an error; it is not recorded as successfully delivered.
- Daily quota counts **recipient addresses**, not API calls; failed or uncertain provider attempts consume quota to reduce retry abuse. No email is sent on navigation, login or page load.
- Run `python -m pytest -q backend/tests/test_vor_v1_3.py` from `backend/` adjusting path to `tests/test_vor_v1_3.py`. Run frontend `npm run typecheck`/`npm run build` locally.
- Never commit `.env`, email secrets, actual private contacts or SQLite DB. Added demos should use fictional identifiers only.

## Verified by patch author

- Nine backend tests passed in isolated test environment including original v1-v1.2 regressions and new v1.3 tests. Previous v1 export migration assertion updated from exactly one marker to ≥3 installed demo migrations.
- TSX syntax transpilation: no diagnostics.
- Full Next.js production build/browser screenshots not run in this isolated environment.

## Next

1. Install v1.3 patch over v1.2, preserve SQLite, test Manage locally.
2. Verify compact panel and dashed/grey Chatter at 1440×900 and 1920×1080.
3. Configure live Resend in backend hosting environment; **do not** deploy until receiver domains and persistence expectations are understood.
4. Consider removing synthetic sender branding if presenting outside private demo; real KEY2/HOTH integration is explicitly out of scope.

## Patch v1.3.1 — wildcard recipient domain policy

- `VOR_DEMO_ALLOWED_EMAIL_DOMAINS=*` now explicitly permits **any email domain** for active subscribed contacts.
- Exact allowlisting via `VOR_DEMO_ALLOWED_RECIPIENTS` and ordinary domain restrictions continue to work when `*` is absent.
- This change only alters the domain policy in `backend/app/api/vor.py` and does **not** auto-send on page load or permit user-supplied recipients in the send request.
- `Manage` remains the only place to add addresses; login and `VOR_DEMO_SEND_REAL_EMAIL=true` are still required to send. Daily recipient cap `VOR_DEMO_EMAIL_LIMIT` is still enforced.
- High risk with weak demo password: any authenticated visitor can add arbitrary recipients then trigger real email. Set a non-guessable password before public deployment, or keep live sending disabled.
- Real mail still needs Resend and a verified sender, public HTTPS link, and persistent storage if contacts must survive service restart.
- Tests include wildcard acceptance for recipients on different domains and continued quota enforcement.
