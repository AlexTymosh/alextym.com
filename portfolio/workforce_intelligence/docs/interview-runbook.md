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

## Reproduce the browser checks locally

Start the Auth and Firestore emulators and set the values documented in the
[Portfolio Lab emulator guide](../../../docs/architecture/portfolio-lab-identity-verification.md#local-emulator-reproduction).
Use `http://127.0.0.1:14300` as `PORTFOLIO_LAB_ORIGIN` and set
`WORKFORCE_INTELLIGENCE_ENABLED=true` in the test processes. Bind Next.js and
FastAPI to localhost on ports `14300` and `14800`. For a disposable Workforce DB,
start FastAPI using the project's `uv` environment from an empty working
directory under `.tmp/`.

With the emulator variables in the current shell, create the fictional Member
and run the desktop walkthrough and authorization tests from the repository root.

```powershell
uv run --project backend python -m scripts.prepare_workforce_emulators
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:14300'
$env:WORKFORCE_MVP_E2E = 'true'
npm --prefix frontend run e2e -- --project=chromium --workers=1 workforce-mvp.spec.ts
```

The browser uses the real Lab sign-in, Next.js BFF and FastAPI host. It verifies
FTE persistence, KPI refresh, evidence links, guides, reset and stale-tab repair.
It also revokes the fictional grant and checks that both hosts reject the same
session. The emulator proves the application flow. Live issuer and HTTPS
verification use the hosted staging check below.

## Hosted acceptance before enabling testers

Use the existing isolated Vercel Preview and Render dev service with the same
Firebase dev project. Record both deployed commits. Scope the two feature flags,
`BACKEND_ORIGIN`, `PORTFOLIO_LAB_ORIGIN` and Firebase configuration to the approved
test environments. Keep Vercel Deployment Protection active. The operator uses
an unexpired dev credential, a fictional test account and the existing grant CLI.
Production flags default to disabled.

1. Verify direct Render health and Preview access. An anonymous browser must
   reach the sign-in gate. Direct Workforce requests without credentials must
   return `401` when enabled.
2. Use an admitted identity with a missing or Fleet-only grant. Verify the
   Workforce page withholds data and that both data origins reject the request.
3. Grant Workforce membership, sign in and complete both walkthroughs, including
   the mutation, reset and prebuilt report. Record the dataset revision and
   generation from successful responses. Verify direct Render with the signed
   test credential and check an untrusted mutation Origin is rejected by Next.js.
4. Revoke the grant and verify the existing credential stops working on both
   origins. Check Fleet and the public site. Record results by environment and
   deployment, then disable the preview flags if the staging window is over.
