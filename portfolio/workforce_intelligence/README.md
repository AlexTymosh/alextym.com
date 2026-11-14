# Workforce & Recruitment Intelligence — embedded portfolio module

**Status:** PR 1, Commit 03 — protected SPA workspace shell implemented; domain
features and the Workforce SQLite database are **not implemented yet**. Both
`PORTFOLIO_LAB_ENABLED` and `WORKFORCE_INTELLIGENCE_ENABLED` remain disabled by
default. Hosted Firebase, Firestore grant and revocation tests are still a release
gate; a locally passing UI test is not authorization evidence.

## Application boundaries

- Catalogue: `/portfolio` (server-guarded and not indexed)
- Application: `/portfolio/workforce-intelligence` (server-guarded, one Next.js page)
- Optional deep link: `/portfolio/workforce-intelligence?mode=people-voice`
- BFF health check: `/portfolio/workforce-intelligence/api/status`
- Direct protected FastAPI status: `/api/workforce/status`
- Existing Fleet URL remains `/fleet-vor-hub`.

Canonical requirements:
[`docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md`](../../docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md).
Implementation ledger: [`SESSION_NOTES.md`](SESSION_NOTES.md).

## Frontend ownership and navigation

The host route mounts only `@workforce-intelligence`. All layout, mode navigation,
scoped styles and UI state remain in `frontend/src/`. The four modes are:

1. Workforce Intelligence (initial view)
2. Workforce Management
3. People Voice
4. Data Architecture

Navigation uses real links with `?mode=`; an unmodified primary click updates
browser history and React state **without a full document reload**. Modified
clicks, opening in a new tab, reloads, and Back/Forward use native browser
semantics. Unknown or duplicate mode values select the default. The URL never
includes credentials, HR records or response text. Internal project theme is
persisted only when local storage is available. No Fleet CSS or components are
imported.

The UI calls only the existing, fixed-origin authenticated status BFF and
reflects its verified result. It distinguishes loading, session expired,
revoked access, disabled demo and backend unavailable; Retry repeats the real
check. None of the feature cards, KPIs or data panels simulate successful
business operations. They explicitly say **Not yet implemented** until PR 2–3.

## Access model — unchanged by Commit 03

1. Firebase Authentication identifies the UID; Portfolio Lab separately admits
   it. A Firebase login alone **never** grants project access.
2. Firestore grant path:
   `portfolio_lab_projects/workforce_intelligence/grants/{firebase_uid}`.
3. A valid Member grant contains `schema_version: 1`, matching `uid` and
   `project_id`, `status: active`, `role: Admin` and optionally a valid future
   `expires_at_ms` timestamp in Unix milliseconds.
4. Project-scoped `Admin` permits the single Workforce `Member` capability
   bundle (including future reset); it grants **no global Owner powers**.
5. The pinned Owner can enter through existing owner credentials. Grant lookup
   is per request and uncached; revocation and Firestore errors fail closed.
6. Next.js page and BFF independently check grants. Render's FastAPI checks
   them again even when the caller bypasses Next.js.
7. Firestore browser rules deny all; credentials are never sent to UI code.

For a trusted operator grant/revoke procedure (dry-run by default):

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD\.tmp\backend-venv"
uv run --project backend python -m scripts.manage_workforce_grant admit-and-grant --uid '<FIREBASE_UID>'
# Review the intended action; --apply makes the actual change.
uv run --project backend python -m scripts.manage_workforce_grant admit-and-grant --uid '<FIREBASE_UID>' --apply
uv run --project backend python -m scripts.manage_workforce_grant revoke --uid '<FIREBASE_UID>' --apply
Remove-Item Env:\UV_PROJECT_ENVIRONMENT
```

This does not create an Auth user/password or send an invitation. Do not use
`admit-and-grant` on an existing admitted UID. The Owner must provision the
Firebase account and use the platform's established password lifecycle.

## Feature flags and hosted verification

`PORTFOLIO_LAB_ENABLED=true` and `WORKFORCE_INTELLIGENCE_ENABLED=true` must be
explicit on **both** Vercel and Render for an authorized hosted preview. Keep
them off until tested. Vercel needs a fixed, validated `BACKEND_ORIGIN`; the BFF
forwards a Firebase session credential to Render. The backend independently
verifies it and reads the authoritative Firestore grant. No frontend-only
protection, `Origin` trust, unsigned headers, or alternate project password.

Manual hosted checks before granting any real visitor access:

1. With flags disabled, `/portfolio`, the app and BFF return 404.
2. With flags enabled, an anonymous visitor is redirected to `/lab/login`, and
   unauthenticated BFF requests return 401.
3. An admitted UID **without** a Workforce grant cannot open the page or use
   its BFF; direct Render access is denied as well.
4. An admitted UID with a valid Workforce grant can open the SPA and receives
   `Protected API verified` after the real status BFF responds.
5. Navigate through all four sections. Verify URL changes without reloading,
   refresh on `?mode=people-voice`, Back/Forward and browser-new-tab navigation.
6. Toggle the internal light/dark theme; test desktop, mobile and keyboard
   focus. All feature cards must still identify missing functionality.
7. Revoke the UID grant; the next protected request must fail, including the
   direct Render origin. Verify safe error state and no leaked records.
8. Simulate Firestore unavailability; the request fails closed. Confirm Fleet,
   public Chat/RAG routes and the website are unaffected.

Live Firebase security, hosted provider behavior and production deployment
have **not** been verified by the local unit tests. Do not claim a released
analytics portal until PR 2–3 supply real data, workflows and acceptance tests.

## Development checks

```powershell
node scripts/check-workforce-scaffold.mjs
# Run from repository root after dependencies are installed.
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run e2e -- workforce-mode-state.spec.ts
# Full repository checks (format, imports, builds, E2E, Docker, etc.).
task ci
```

`frontend/e2e/workforce-mode-state.spec.ts` tests the URL contract without
pretending to have a real admitted browser session. Authenticated browser flows
require the controlled hosted preview outlined above.
