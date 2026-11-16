# Workforce Intelligence interview runbook

## Prepare the demo

Open **Workforce Intelligence** from the public portfolio and enter the demo
password. Confirm that Recruitment overview has loaded and the workspace header
shows the dataset generation. Use **Reset demo** before the 90-second run.
For a five- or ten-minute run with a plotted forecast, choose **Load full dataset**
and confirm the **Controlled baseline** before starting. Both actions replace
the shared synthetic generation. Allow 15 seconds between replacements.

For a cold Render instance, open the workspace early and let the first data
request finish. Use **Retry** if the data service is still starting. People
Voice can open the **Demonstration fallback result** using the persisted fixture.
Its labelled seeded review, evidence IDs and linked action support a live demo
without an AI provider call. Prepare a synthetic Excel workbook from
**Workforce Management → Import / Export → Download template** for the
ten-minute run.

## 90-second walkthrough

1. Select **90-second walkthrough** and **Run interview scenario**. Show
   Workforce gap and Median time to hire for 1–31 October 2026.
2. Select **Next step** to open the effective-dated contract for James W. Change
   contracted FTE from 1.0 to 0.8 effective 20 October 2026. Select **Save FTE**.
3. Select **Next step**. Read the updated Workforce gap from Recruitment overview.
   It increases by 0.2 WTE from the seed and the reporting dates stay the same.
4. Open **Insight Pilot** at the last step. Ask **Explain the vacancy rate** and
   show the open and budgeted WTE figures behind 14.29%.

## Five-minute walkthrough

Select **Five-minute walkthrough**. Repeat the FTE change and check the
resulting gap. The guide opens the application funnel, candidate feedback,
People Voice, forecasting, Insight Pilot and Data Architecture.

- In the funnel, select **Advisor intake**. Its application counts and
  conversions use distinct applications in the reporting window.
- Open **Rating question results** in the prepared candidate report and compare
  the response rate and ratings with the recorded application indicators.
- Open **Rota Changes and Workforce Pressure**. The fixture has 12 responses
  and 10 analysable comments. Follow `rota-001` from the published finding and
  show the separate seeded review and linked management action.
- Open the **Workforce gap** definition. It includes effective budget WTE,
  substantive WTE, date window, quality and version.
- Select **Enable forecast**. The controlled full fixture shows a dashed
  projection, the start month, training dates and rolling error against
  seasonal naïve. The short fixture shows the insufficient-history message.
- Explain the vacancy rate in Insight Pilot. In Data Architecture, compare the
  Operational, Bronze and Silver example for one contract. Verify the Gold
  gap against Recruitment overview at the same cutoff.

## Ten-minute walkthrough

Select **Ten-minute walkthrough** for the five-minute sequence plus these steps.

1. Upload the synthetic workbook and select **Validate workbook**. Show the
   row checks and projected dashboard impact before committing changes.
2. Change **Pre-employment checks (days)** or **Offer acceptance (%)** and
   select **Run scenario**. Compare starts, open vacancy WTE and workforce gap
   with the reference. Open the assumptions panel to explain internal moves.
3. Choose a generated campaign. Run **Analyze with demo fallback**, inspect
   the evidence IDs and excerpt, then confirm or amend a supported finding
   with a rationale. Publish it separately. If the narrow candidate sample
   suppresses a finding, use a larger generated staff campaign and the
   [People Voice walkthrough](people-voice.md).
4. In the action tracker, create a management action tied to the published
   finding and record its target, due date and progress.
5. Open **People Voice to Action**. Select the structured evidence gateway to
   show the invalid JSON and unsupported-evidence paths.
6. Open **Audit history** to find the source edit or review event, then show
   the date and issue counts in **Data quality checks**.

The guide restores its active step on reload and opens the relevant panel.
Normal navigation and reporting dates remain available. Guided navigation
leaves source changes, generation, publication and imports to the presenter.

## Optional PR4 Excel demonstration

Use the disposable synthetic Workforce environment and a valid demo session.
For a predictable baseline, choose **Reset demo** and confirm before starting.

1. Open **Workforce Management → Import / Export** and select **Download template**.
2. Populate the **Employees** sheet with a fictional employee code and a display
   alias such as `Aria P.`. Keep the workbook metadata, exact sheet headers
   and the required fields; use an existing establishment line ID. The current
   accepted actions and keys are in [Excel import/export](workbooks.md).
3. Upload the workbook and select **Validate workbook**. Confirm the row-level
   preview and projected **Dashboard impact**. No employee should appear in the
   operational records before the import is confirmed.
4. Select **Apply these changes to the shared demo**, then **Confirm import**.
   Confirm the receipt, audit trail, new dataset revision and updated Gold metric.
5. Download a scoped **Filtered analytics** workbook and confirm the synthetic
   disclosure and reporting period. Finally, reset the disposable dataset.

The preview expires after 15 minutes. Concurrent edits or reset require another
validation. Use a new fictional employee ID for each committed run.

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
npm run dev -- --hostname 127.0.0.1 --port 14300
```

3. **E2E**, from the repository root:

```powershell
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:14300'
$env:WORKFORCE_PASSWORD_E2E = 'true'
$env:WORKFORCE_E2E_PASSWORD = '<local-test-password>'
npm --prefix frontend run e2e -- --project=chromium --workers=1 workforce-mvp.spec.ts workforce-people-voice.spec.ts workforce-transport.spec.ts workforce-release.spec.ts
```

`WORKFORCE_E2E_PASSWORD` is a **local testing variable**, not a browser
configuration or a checked-in credential. The workbook import test additionally
requires a synthetic `WORKFORCE_OPS_XLSX_FILE`. Verify that test output does
not report all authenticated scenarios as skipped.

## Hosted acceptance before sharing the demo

After the merge, confirm the frontend and shared FastAPI backend are serving
the approved revision. Vercel uses the configured HTTPS `BACKEND_ORIGIN`.
Both services require `WORKFORCE_INTELLIGENCE_ENABLED=true`. Render owns
`VOR_DEMO_PASSWORD`. The Workforce origin check uses the routed Vercel host.

1. With the Workforce flag absent, the page and API return 404.
2. With the flag enabled, an anonymous visitor sees the logo and password form.
   API access and direct Render Workforce data calls must return 401.
3. A wrong password returns 401; repeated invalid attempts receive 429.
4. Sign in with the existing demo password. A valid Workforce session has an
   eight-hour HttpOnly cookie. A Fleet cookie fails Workforce authorization.
5. Open the executive KPIs, prepared surveys, forecast toggle and Data Architecture.
   Time the warm dashboard and a filtered query. Targets are three and two seconds
   respectively under normal hosted conditions. An unseeded Render instance may
   take longer and offers retry after a transport failure.
6. Verify cross-origin write rejection, reload with a valid session, and sign-out.
   Use the disposable local test environment for dataset replacement or imports
   when a hosted walkthrough is in progress.
7. Check the public catalogue, Fleet and host health. Record the Vercel and Render
   revision separately with the observed results.

The request ID links the HTTP endpoint, latency and status to safe run metadata
in logs. Analysis entries identify the model and prompt version. Structured
provider usage is recorded when supplied. Workbook validations log the batch
and invalid-row count. Forecast logs record completion or insufficient history.

To take Workforce offline, disable its flag on both surfaces. To roll back a
deployment after a newer Workforce schema has been used, redeploy the previous
approved build and regenerate the disposable Workforce database with that
revision. The project owns only `.tmp/workforce/workforce.sqlite3`.
[Password-demo access](password-demo-access.md)
