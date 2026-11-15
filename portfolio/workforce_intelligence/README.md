# Workforce & Recruitment Intelligence â€” portfolio demonstration

**Temporary access:** shared Fleet demo password, no Firebase. The system is a
synthetic-data simulation and is not an official SCAS or NHS product.

## Open the demo

Open `/portfolio/workforce-intelligence`. The landing page displays the project
emblem and a short description beside a password form. Enter the **same demo
password** used at `/fleet-vor-hub`. After sign-in, the existing Workforce
Intelligence UI opens. Sign out from the app header.

- `WORKFORCE_INTELLIGENCE_ENABLED=true` must be set on Vercel and Render.
- `VOR_DEMO_PASSWORD` stays **only on Render** (Fleet already uses it).
- `BACKEND_ORIGIN=https://<your-render-origin>` must be set on Vercel.
- `PORTFOLIO_LAB_ORIGIN=https://<canonical-site-origin>` must be set on Vercel
  for same-origin password and mutation checks.
- Keep `PORTFOLIO_LAB_ENABLED` and Firebase independent; Workforce no longer
  requires them. Both features default to disabled.
- Do not use this password-only mode for real workforce/employee information.

See [temporary password access](docs/password-demo-access.md) for security
constraints, setup, and release checks.

## Application

- `/portfolio`: simple list of enabled demonstrations.
- `/portfolio/workforce-intelligence`: password gate and the four-mode UI.
- `/portfolio/workforce-intelligence/api/*`: same-origin BFF to protected FastAPI.
- `/portfolio/workforce-intelligence/preview`: development-only offline UI.

The UI retains Workforce Intelligence, Workforce Management, People Voice,
and Data Architecture. Its SQLite operational model and all KPI/reporting logic
are unchanged. Password sessions are scoped to Workforce; they are **not** Fleet
cookies, Firebase sessions, or per-person identities.

## Reference documentation

- [Technical Specification v1.2](../../docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md)
- [Implementation plan](SESSION_NOTES.md)
- [Data architecture](docs/architecture.md)
- [Synthetic source dictionary](docs/data-dictionary.md)
- [API](docs/api.md)
- [Metrics catalogue](docs/metric-catalogue.md)
- [Assurance and source register](docs/assurance-register.md)
- [Interview walkthrough](docs/interview-runbook.md)

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
