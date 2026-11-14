# Workforce & Recruitment Intelligence — embedded portfolio module

**Status:** Commit 02 — explicit platform grants and secure BFF transport implemented;
**disabled by default** until environment and hosted access checks are completed.
Business dashboards, workflows, demo SQLite, and SPA shell remain future commits.

## Application boundaries

- Catalogue: `/portfolio` (protected; only accessible projects shown)
- Entry: `/portfolio/workforce-intelligence` (protected Next.js route)
- BFF status: `/portfolio/workforce-intelligence/api/status` (fixed backend target)
- Direct Render API: `/api/workforce/status` (also independently protected)
- Fleet legacy route remains `/fleet-vor-hub`.

The spec is at
[`docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md`](../../docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md).
Execution history lives in [`SESSION_NOTES.md`](SESSION_NOTES.md).

## Access model

1. An existing Firebase email/password account has a **verified UID** and an **active Portfolio Lab admission**.
2. A central Firestore grant exists at:
   `portfolio_lab_projects/workforce_intelligence/grants/{firebase_uid}`.
3. It must contain `schema_version: 1`, `project_id: workforce_intelligence`,
   `uid: <exact Firebase UID>`, `status: active`, `role: Admin`.
4. An optional `expires_at_ms` (integer Unix milliseconds) may limit validity.
   If omitted, the grant is indefinite. A malformed/expired value denies access.
5. `Admin` is a **project-scoped platform capability** needed for the uniform
   Workforce `Member` (including future reset). It **does not** grant global Owner authority.
6. The pinned Owner authenticated via the existing platform can enter without a
   project grant. A password account alone, or a Fleet grant, is insufficient.
7. The Next.js page/BFF and direct FastAPI origin independently enforce this
   policy. Firestore is read on each protected request to apply revocation promptly.

All browser Firestore access remains forbidden by existing deny-all Firestore rules.
Never send Firebase Admin service credentials to browser code or to a visitor.

## Feature flags (both deployments)

Set **both** `PORTFOLIO_LAB_ENABLED=true` and
`WORKFORCE_INTELLIGENCE_ENABLED=true` on the Vercel and Render environments
only for a controlled preview after verifying grant behavior. Otherwise routes
remain unavailable (404). The feature flag is not a substitute for a grant.

On Vercel, `BACKEND_ORIGIN` must point to the explicitly configured Render
origin; the status BFF forwards a revocation-checked Firebase session cookie
as a credential, not as an identity assertion. Render checks it independently.

## Operator grant and revoke

Only from a trusted **operator** environment with Firebase Admin credentials,
matching `FIREBASE_PROJECT_ID` and a configured `PORTFOLIO_LAB_OWNER_UID`.
The global Owner first provisions Firebase Auth credentials. If the platform
admission record does not yet exist, use `admit-and-grant` once. This is an
operator-only step, never an HTTP endpoint or a browser action.

```powershell
# Run from repository root. Default is dry-run.
$env:UV_PROJECT_ENVIRONMENT = "$PWD\.tmp\backend-venv"
uv run --project backend python -m scripts.manage_workforce_grant admit-and-grant --uid '<FIREBASE_UID>'
# Inspect the intended UID and action. Only then explicitly apply.
uv run --project backend python -m scripts.manage_workforce_grant admit-and-grant --uid '<FIREBASE_UID>' --apply
# For an existing active admission record, use the `grant` action instead.
# Revoke immediately (uncached checks on both servers).
uv run --project backend python -m scripts.manage_workforce_grant revoke --uid '<FIREBASE_UID>' --apply
Remove-Item Env:\UV_PROJECT_ENVIRONMENT
```

`admit-and-grant` creates an active admission with a **90-day initial-password
expiry**. Do not reuse it for an existing admitted UID or confuse it with
changing the Firebase Auth password itself.

Every committed operation is atomically paired with an audit event in
`portfolio_lab_grant_events`; neither the grant nor event is stored in
Workforce's disposable SQLite. This CLI does not create users, passwords,
or invitation emails and is not exposed as an HTTP endpoint.

## Verify

```powershell
node scripts/check-workforce-scaffold.mjs
uv run --project backend python -m pytest backend/tests/test_workforce_grants.py backend/tests/test_workforce_scaffold.py backend/tests/test_workforce_grant_cli.py -q
task ci
```

Local unit tests and default-off E2E are **not** live Firebase security evidence.
Before enabling real participants, validate grant, denial, revocation, failed
Firestore reads, SSR and BFF, and direct Render API on an isolated hosted
preview, using temporary synthetic credentials and no real HR data.
