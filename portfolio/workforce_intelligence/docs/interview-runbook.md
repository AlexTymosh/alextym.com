# Workforce Intelligence interview MVP

## Prepare the demo

Open Portfolio Lab and select Workforce Intelligence with the provisioned Member
account. Confirm that Recruitment overview has loaded and the workspace header
shows the dataset generation. Use **Reset demo** and confirm before each
recorded walkthrough. Reset replaces the shared Workforce fixture, records an
audit event and increments the generation. A second reset within 15 seconds
returns a retry interval.

For a cold Render instance, open the workspace early and let the first data
request finish. Use **Retry** if the data service is still starting. People
Voice can open the **Demonstration fallback result** using the persisted fixture.
Its labelled seeded review, evidence IDs and linked action support a live demo
without an AI provider call.

## 90-second walkthrough

1. Select **90-second walkthrough** and **Run interview scenario**. Show
   Workforce gap and Median time to hire for 1–31 October 2026.
2. Select **Next step** to open the effective-dated contract for Demo A. Change
   contracted FTE from 1.0 to 0.8 effective 20 October 2026. Select **Save FTE**.
3. Select **Next step**. Read the updated Workforce gap from Recruitment overview.
   It increases by 0.2 WTE from the seed and the reporting dates stay the same.
4. Open **Insight Pilot** at the last step. Ask **Explain the vacancy rate** and
   show the open and budgeted WTE figures behind 14.29%.

## Five-minute walkthrough

Select **Five-minute walkthrough** after the baseline reset. Repeat the FTE
change and check the resulting gap. The guide then opens the application funnel,
People Voice, metric definition, Insight Pilot and Data Architecture.

- In the funnel, select **Advisor intake**. Its application counts and
  conversions use distinct applications in the reporting window.
- Open **Rota Changes and Workforce Pressure**. The fixture has 12 responses
  and 10 analysable comments. Follow `rota-001` from the published finding and
  show the separate seeded review and linked management action.
- Open the **Workforce gap** definition. It includes effective budget WTE,
  substantive WTE, date window, quality and version.
- Show the approved Insight Pilot calculation and trace it from Workforce
  SQLite through Bronze and Silver to Gold. The published survey results have
  their own evidence-and-review gate.

The guided links retain the active step across a reload. Normal navigation and
date controls are available throughout the demo. Candidate experience analysis,
forecasting and live analyst publication are planned for later stages.

## Optional PR4 Excel demonstration

Use only the separate synthetic Workforce environment and a permitted Member account.
For a predictable baseline, choose **Reset demo** and confirm before starting.

1. Open **Workforce Management → Import / Export** and select **Download template**.
2. Populate the **Employees** sheet with a fictional employee code and a display
   alias beginning with `Demo`. Keep the workbook metadata, exact sheet headers
   and the required fields; use an existing establishment line ID. The current
   accepted actions and keys are in [Excel import/export](workbooks.md).
3. Upload the workbook and select **Validate workbook**. Confirm the row-level
   preview and projected **Dashboard impact**. No employee should appear in the
   operational records before the import is confirmed.
4. Select **Apply these changes to the shared demo**, then **Confirm import**.
   Confirm the receipt, audit trail, new dataset revision and updated Gold metric.
5. Download a scoped **Filtered analytics** workbook and confirm the synthetic
   disclosure and reporting period. Finally, reset the disposable dataset.

The preview expires after 15 minutes; concurrent source edits or dataset reset
require another validation. Do not reuse employee IDs or real workforce data.
The local emulator checks are not a substitute for staged HTTPS/grant verification.

Desktop screenshots from the authenticated local emulator run show the
[Recruitment overview](screenshots/workforce-recruitment.png) and the
[People Voice fallback report](screenshots/workforce-people-voice.png).

## Reproduce the password-demo browser checks locally

Firebase and Firestore are **not required** for the temporary Workforce demo.
Use a disposable SQLite database and the same synthetic password in the FastAPI
process and the test runner. A working example with three PowerShell terminals:

1. **Backend**, from `backend` (set these variables in this terminal):

```powershell
$env:WORKFORCE_INTELLIGENCE_ENABLED = 'true'
$env:VOR_DEMO_PASSWORD = '<local-test-password>'
$env:ENVIRONMENT = 'test'
$env:FRONTEND_ORIGIN = 'http://127.0.0.1:14300'
uv run uvicorn app.main:app --host 127.0.0.1 --port 14800
```

Run FastAPI in an **isolated disposable working directory** if you want a fresh
`.tmp/workforce/workforce.sqlite3`. This project owns its database path; do not
reuse an existing shared demo database for mutation or reset browser tests.

2. **Frontend**, from `frontend`:

```powershell
$env:WORKFORCE_INTELLIGENCE_ENABLED = 'true'
$env:BACKEND_ORIGIN = 'http://127.0.0.1:14800'
$env:PORTFOLIO_LAB_ORIGIN = 'http://127.0.0.1:14300'
npm run dev -- --hostname 127.0.0.1 --port 14300
```

3. **E2E**, from the repository root:

```powershell
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:14300'
$env:WORKFORCE_PASSWORD_E2E = 'true'
$env:WORKFORCE_E2E_PASSWORD = '<local-test-password>'
npm --prefix frontend run e2e -- --project=chromium --workers=1 workforce-mvp.spec.ts
```

`WORKFORCE_E2E_PASSWORD` is a **local testing variable**, not a browser
configuration or a checked-in credential. The workbook import test additionally
requires a synthetic `WORKFORCE_OPS_XLSX_FILE`. Verify that test output does
not report all authenticated scenarios as skipped.

## Hosted acceptance before sharing the demo

Deploy the same commit on an isolated Vercel Preview and Render dev service.
Render must retain `VOR_DEMO_PASSWORD`; Vercel must never receive it. Both
services require `WORKFORCE_INTELLIGENCE_ENABLED=true`, while Vercel requires
`BACKEND_ORIGIN` and the canonical `PORTFOLIO_LAB_ORIGIN` for CSRF protection.
Keep Vercel deployment protection enabled for the preview.

1. With the Workforce flag absent, the page and API return 404.
2. With the flag enabled, an anonymous visitor sees the logo and password form.
   API access and direct Render Workforce data calls must return 401.
3. A wrong password returns 401; repeated invalid attempts receive 429.
4. The correct **Fleet demo password** grants access to Workforce but a Fleet
   cookie cannot authorize Workforce data. Verify an 8-hour HttpOnly cookie.
5. Check executive KPIs, vacancy drill-through, Inclusive Recruitment masking,
   People Voice and the four SPA modes using synthetic data only.
6. Confirm API writes still reject an invalid Origin; refresh preserves a valid
   session; logout removes browser access; a rotated password invalidates tokens.
7. Check that Fleet and public website endpoints are unaffected. Record status
   by deployment SHA; keep the preview disabled after testing if appropriate.

See [password-demo access](password-demo-access.md) for the threat model. This
mode is **not** suitable for personally identifiable or clinical workforce data.
