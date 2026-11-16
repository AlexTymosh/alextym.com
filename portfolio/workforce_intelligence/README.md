# Workforce & Recruitment Intelligence â€” portfolio demonstration

**Temporary access:** shared Fleet demo password, no Firebase. The simulation
uses synthetic data.

## Open the demo

Open `/portfolio/workforce-intelligence`. The landing page displays the project
emblem and a short description beside a password form. Enter the **same demo
password** used at `/fleet-vor-hub`. After sign-in, Workforce Intelligence opens
as a full-page workspace. Sign out from the Workforce header.

- `WORKFORCE_INTELLIGENCE_ENABLED=true` must be set on Vercel and Render.
- `VOR_DEMO_PASSWORD` stays **only on Render** (Fleet already uses it).
- `BACKEND_ORIGIN=https://<your-render-origin>` must be set on Vercel.
- Keep `PORTFOLIO_LAB_ENABLED` and Firebase independent; Workforce no longer
  requires them. Both features default to disabled.
- Do not use this password-only mode for real workforce/employee information.

See [temporary password access](docs/password-demo-access.md) for security
constraints, setup, and release checks.

## Application

- `/portfolio`: public catalogue cards for Fleet VOR Hub and Workforce.
- `/portfolio/workforce-intelligence`: password gate and the four-mode UI.
- `/portfolio/workforce-intelligence/api/*`: same-origin BFF to protected FastAPI.
- `/portfolio/workforce-intelligence/preview`: development-only offline UI.

The UI includes recruitment and workforce analysis, effective-dated edits and
Excel import, People Voice campaigns and review, and live SQLite lineage with a
People Voice to Action process diagram. Forecasting compares seasonal naïve
and exponential smoothing. What-if scenarios show the effect of recruitment
assumptions on expected starts and WTE. The Workforce session uses a
project-scoped cookie and a shared demo identity.

## Reference documentation

- [Technical Specification v1.2](../../docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md)
- [Implementation plan](SESSION_NOTES.md)
- [Data architecture](docs/architecture.md)
- [Synthetic source dictionary](docs/data-dictionary.md)
- [API](docs/api.md)
- [Metrics catalogue](docs/metric-catalogue.md)
- [Assurance and source register](docs/assurance-register.md)
- [Interview walkthrough](docs/interview-runbook.md)
- [Forecasting and what-if methods](docs/planning.md)
- [People Voice walkthrough](docs/people-voice.md)

## Validation

From the repository root:

```powershell
task backend:format
task ci
git diff --check
```

For real browser E2E, configure an isolated password-demo Render/FastAPI and
Next.js localhost environment; set `WORKFORCE_PASSWORD_E2E=true`,
`WORKFORCE_E2E_PASSWORD` (test secret, never checked in), and
`PLAYWRIGHT_BASE_URL=http://127.0.0.1:14300`. The Firebase/Firestore emulator
procedures in older runbooks are **historical** and not required for this mode.
Always run browser tests with a disposable synthetic Workforce database.
