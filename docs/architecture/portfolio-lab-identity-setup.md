# Portfolio Lab — Firebase identity integration checkpoint (PR 2)

**Status:** Owner-only, feature-disabled by default; this is the first PR 2 code increment, not the completed identity/access solution.

The [requirements specification](../specifications/portfolio-lab-auth-access.md) and [ADR-0001](../adr/0001-portfolio-lab-identity-access.md) remain authoritative.

## Architecture proven by this increment

- Next.js sign-in is implemented at `/lab/login` with Firebase client Auth providers: Google, Microsoft (`microsoft.com`), GitHub, and email/password.
- The browser exchanges a *recently authenticated* Firebase ID token for a five-day, HttpOnly, Secure-in-production, SameSite=Strict session cookie via `/lab/session`. This route lives outside `/api/*` so it is **not** forwarded to Render by the existing Next rewrite.
- Next.js server-rendered `/lab` requires a verified, non-revoked Firebase session cookie and the pinned `PORTFOLIO_LAB_OWNER_UID`.
- FastAPI independently checks Firebase ID tokens in `Authorization: Bearer` via `/api/lab/identity`. This endpoint does not trust browser cookies, Host, Origin, or request payload for identity, and permits only the pinned Owner. It can be called directly on Render and denies missing/invalid tokens.
- Both paths are disabled by default, and neither grants access to Fleet VOR Hub or any other project.
- On-screen linking calls Firebase `linkWithPopup` on the currently signed-in UID. It never automatically merges two existing Firebase accounts when different emails or a provider collision occur.

## Environment variables

### Next.js (Vercel / frontend local)

```dotenv
PORTFOLIO_LAB_ENABLED=false
PORTFOLIO_LAB_OWNER_UID=<trusted-firebase-uid>
NEXT_PUBLIC_FIREBASE_API_KEY=<web-api-key>
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=<project-id>.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=<project-id>
NEXT_PUBLIC_FIREBASE_APP_ID=<web-app-id>
FIREBASE_PROJECT_ID=<project-id>
# Choose ONE server credential route, not both:
FIREBASE_SERVICE_ACCOUNT_JSON=<service-account-json-secret>
# Or use a managed Google Application Default Credential outside the repo.
```

### FastAPI (Render / backend local)

```dotenv
PORTFOLIO_LAB_ENABLED=false
PORTFOLIO_LAB_OWNER_UID=<same-trusted-firebase-uid>
FIREBASE_PROJECT_ID=<same-project-id>
FIREBASE_SERVICE_ACCOUNT_JSON=<service-account-json-secret>
```

All `NEXT_PUBLIC_*` values are public client application identifiers; **never** use them to store server secrets. The Firebase service-account credential is a backend/Next-server **secret**, not a client variable. Do not commit real credentials or initial passwords. Do not enable the Lab on production before the Owner UID and direct-Render checks are verified.

### Provider setup checklist (Firebase Console)

1. Create a **development Firebase project** and register a web app. Enable Email/Password and Google under Authentication → Sign-in method.
2. Configure Microsoft and GitHub OAuth providers with their application/client IDs and secrets in Firebase Authentication. Add each provider's exact Firebase OAuth redirect/callback URL to its own provider console. The Microsoft organisation/Entra tenant may restrict consent or sign-in.
3. Under Firebase Authentication → Settings → Authorized domains, register the local test domain and the approved preview/production hostnames as appropriate. Do not add wildcard or arbitrary domains.
4. Create or sign in as a test Owner in Firebase Console; copy the immutable **Firebase UID**, not an email address, to `PORTFOLIO_LAB_OWNER_UID` in both services.
5. Configure trusted service-account credentials only in local ignored `.env` files or Vercel/Render secrets. Use one Firebase project per environment where practical. Rotate exposed secrets immediately.
6. While developing, leave `PORTFOLIO_LAB_ENABLED=false` in production. For a dedicated development deployment set `true` and verify `/lab/session`, `/lab`, logout, linking, and a direct-call attempt to Render's `/api/lab/identity` using an owner/non-owner/invalid ID token.

## Dependencies and local test commands

In a new `feat/portfolio-firebase-identity` branch created from latest `main`:

```powershell
Push-Location frontend
npm install firebase firebase-admin
Pop-Location
Push-Location backend
uv add 'firebase-admin>=7,<8'
Pop-Location

task backend:format
task backend:test
task frontend:check:ci
task ci
```

`npm install` updates `frontend/package.json` and `frontend/package-lock.json`; `uv add` updates `backend/pyproject.toml` and `backend/uv.lock`. Commit both lockfiles. The exact compatible version available at install time should be checked; do not bypass lockfile consistency or GitHub CI.

## Cross-host identity transport (second PR 2 increment)

A five-day website cookie does **not** automatically reach the Render domain. A
Firebase `browserSessionPersistence` ID token can also disappear when the browser
tab closes. The architecture therefore uses an explicit **same-origin BFF** for
server-side protected requests, instead of relying on browser persistence:

1. `GET /lab/api/identity` runs in Next.js (it is not covered by `/api/*` rewrites).
2. Next.js verifies its own HttpOnly Firebase session cookie with revocation
   checking and checks the configured Owner UID. It does not send the cookie
   back to JavaScript or accept a user-controlled backend URL.
3. Next.js forwards the signed Firebase session cookie **server-to-server** only
   to the fixed `BACKEND_ORIGIN` as `Authorization: FirebaseSession <cookie>`.
   In production, `BACKEND_ORIGIN` must use HTTPS with no URL path/credentials.
4. FastAPI verifies that Firebase session cookie independently (signature,
   expiry, revocation and project) and checks the same pinned Owner UID. Direct
   Render requests with no valid credentials remain denied.
5. FastAPI also retains the direct test protocol
   `Authorization: Bearer <Firebase-ID-token>`. The schemes are **not** fallback
   alternatives: invalid ID tokens cannot be reinterpreted as session cookies.

The probe deliberately does not expose project functionality and is not a
substitute for Firestore grants and capabilities (PR 3). This design avoids
long-lived Firebase ID tokens in browser local storage, and supports private
server-side calls even after a browser tab is closed. It does **not** make
browser-to-Render CORS work automatically; future protected browser operations
must use an explicit same-origin BFF or a fresh ID token validated by Render.

For development smoke tests with `PORTFOLIO_LAB_ENABLED=true`, configure a local
`BACKEND_ORIGIN` for Next.js and enable the Owner UID in both environments:

- Without a cookie: `GET /lab/api/identity` returns 401.
- With a valid Owner cookie and a reachable backend: returns 200.
- A revoked/wrong-owner cookie or direct unauthenticated request to Render:
  returns 401/403 as appropriate.
- Backend offline: the probe returns 502; `/lab` login and dashboard do not
  depend on Render availability.

**Still blocking PR 2 release:** invited-user admission, initial-password
expiry/change reconciliation, full provider/linking/recovery tests, and live
cross-origin smoke. Keep the Lab feature flag off in production.

## Security integration gates still outstanding

This is **not** an admission/RBAC release. Before PR 2 is ready for merge, implement and test the remaining identity requirements:

- Secure invitation and identity-claim process for users other than Owner, not simply trusting a matching email.
- Initial password validity from 1 to 90 days, with server enforcement that cannot be bypassed by immediately exchanging a password-derived ID token for a long-lived session. The credential type and password age must be verified against trusted metadata; no native Firebase expiry is assumed.
- Password-setup links and recovery with non-Owner users; no separate email-verification step, but proof of mailbox ownership through setup link where needed.
- Real-provider tests for Microsoft, Google, GitHub, linking accounts with different emails, existing-credential collisions and corporate tenant restrictions.
- Session revocation, token expiry, CSRF/Origin checks, backend direct-origin verification, and sign-out behavior.
- A policy for browser Firebase Auth persistence vs. server cookie: this increment uses browser-session persistence; new tabs may require re-sign-in for direct FastAPI bearer calls until a finished BFF/token-transport design is implemented.

**Do not turn on the new Fleet authorization or send real project emails under this temporary Owner-only identity probe.** PR 3 owns Firestore-backed grants, and PR 5/6 own Fleet migration and live mail controls.

## Durable identity admission and initial-password gate (third PR 2 increment)

Both Next.js and FastAPI now reject all non-Owner Firebase UIDs unless a
**server-side Firestore** document exists at `portfolio_lab_identities/{uid}`.
The pinned Owner UID is the only special case. The Firestore SDK uses the named
`portfolio-lab` Firebase Admin app; the browser must never read or write this
collection. Firestore rules must deny all client access to the control plane.

Schema version `1` (exact fields used by both runtimes):

```json
{
  "schema_version": 1,
  "uid": "trusted-firebase-uid",
  "status": "active",
  "password_state": "initial",
  "initial_password_expires_at_ms": 1800000000000
}
```

- `status` must be exactly `active`; `invited`, `disabled`, absent and malformed
  documents are denied. Never treat Firebase email or display name as an invite.
- `password_state` must be `initial`, `user_set`, or `none`. An initial password
  is denied at/after `initial_password_expires_at_ms` for password sign-in, even
  if a five-day session was issued earlier. A legitimately linked OAuth provider
  can still authenticate the same UID; initial password expiry is not account
  revocation. `none` forbids password admission.
- `user_set` is a **trusted server-side transition**, not a client field. Never
  flip it based solely on a user's assertion or a password-reset email request.
  Account provisioning, password-reset confirmation, partial-failure recovery,
  and invite delivery are still pending and must precede enabling non-Owner users.
- Document UID must equal the verified Firebase UID. Invalid metadata, unknown
  providers and Firestore errors fail closed; no grants or project permissions
  are created by this increment. In PR 3, each project must check its own grant
  independently on every protected request.
- Only the pinned Owner can enter the identity preview without a Firestore
  identity document. Do not infer Owner from an email address.
- `docs/contracts/portfolio-lab-admission-cases.json` is the shared set of
  deterministic allow/deny cases tested by Next.js and FastAPI. These tests do
  not exercise real Firebase or Firestore connectivity.

**Deployment:** Keep `PORTFOLIO_LAB_ENABLED=false` in production. A real
non-Owner onboarding flow is not available until an auditable Owner-only
provisioning path and password replacement/recovery are implemented. Configure
one restricted development Firestore project before running live smoke tests.

Recommended rules are checked in at `infra/firebase/firestore.rules`; publish
them to the **development Firebase project** in Firebase Console before
creating identity documents. This file is not deployed automatically. Admin
SDK server credentials bypass Firestore client rules and must be protected with
least-privilege IAM.
## Owner-only initial-password provisioning increment

Development-only command: [Owner provisioning runbook](portfolio-lab-provisioning.md).
Creates a **new** disabled Firebase UID, commits an `invited` identity and an audit
record, enables Firebase Auth, then atomically activates the identity with a
second audit event. Initial credential expiry is 1–90 days and admission remains
separate from project grants. There is no public provisioning endpoint, setup
link, password-reset reconciliation, or automatic notification in this increment.
Keep Portfolio Lab disabled on production until the remaining security gates pass.

## Owner-generated password setup and recovery (fifth PR 2 increment)

This feature requires an explicitly configured **development** Firebase project.
No password reset link is delivered automatically, and no project grant is created.

### Identity and reset-code protocol

- `scripts.generate_lab_setup_link` is an Owner-only local CLI, gated by
  `PORTFOLIO_LAB_PROVISIONING_ENABLED=true`, a pinned Owner UID, and an exact
  `--project-id` match. `--create-user` creates a new Auth user initially
  disabled, with an unguessable undisclosed bootstrap password, writes an
  `invited`/`password_state=none` Firestore identity and audit, and then enables
  the Auth user. It **does not** activate application admission.
- Existing users must already have a `portfolio_lab_identities/{uid}` record
  with `status=invited|active`, supported password state, and a non-disabled
  Firebase Auth user. Never adopt an arbitrary Auth account by matching email.
- The Admin SDK generates a provider password-reset action code. The CLI moves
  that code from Firebase's generated URL query into a private
  `/lab/password/reset#oobCode=...` link at an explicitly approved HTTPS origin.
  Fragments are not sent in the initial page HTTP request, but the link still
  contains a **bearer secret** and must be delivered confidentially. Do not
  paste it into source control, tickets or shared logs.
- The browser removes the URL fragment from history before accepting the new
  password and POSTs the code and password to a same-origin route. The route
  validates Origin, media type and request size; it does not expose UID/email.
- The Next.js server first inspects the code using the documented Firebase
  Identity Toolkit `accounts:resetPassword` REST API *without consuming it*;
  it checks the resolved Firebase UID against the Firestore identity record.
  It then confirms the code with `newPassword` at the **fixed** provider URL,
  compares the returned email/UID, revokes Firebase refresh tokens, and
  transactionally sets `password_state=user_set`, activates an `invited`
  account and creates an audit event. The transaction rechecks the current UID
  and status to prevent entitlement resurrection. The project remains without
  grants until the RBAC phase.
- `PORTFOLIO_LAB_ENABLED=false` keeps both the page and the endpoint absent.
  The public login screen no longer triggers an untracked provider reset email;
  it directs users to request a private link from the Owner.

### Development operator command

Run `uv run python -m scripts.generate_lab_setup_link` from `backend`:

```powershell
# Dry run, no Firebase reads/writes:
uv run python -m scripts.generate_lab_setup_link `
  --email invitee@example.test --project-id dev-project `
  --origin https://dev.example.test --create-user

# Only after secrets, Firebase rules and UID have been verified:
$env:PORTFOLIO_LAB_PROVISIONING_ENABLED = "true"
uv run python -m scripts.generate_lab_setup_link `
  --email invitee@example.test --project-id dev-project `
  --origin https://dev.example.test --create-user --apply
Remove-Item Env:\PORTFOLIO_LAB_PROVISIONING_ENABLED
```

For **existing** accounts, omit `--create-user`. This is a privileged command,
not an HTTP endpoint. It prints the one-time link once; no email is sent.
Change/reset code lifetime is controlled by Firebase, **not** by the 90-day
initial-password rule. To recover an expired/consumed link, issue a new one.

### Partial-failure and security limitations

- Firebase Auth and Firestore are separate services and cannot share one atomic
  transaction. If code redemption succeeds but refresh-token revocation or
  Firestore commit fails, the route returns an error; do not infer successful
  admission. Issue a new link and reconcile the UID with an Owner action.
- Invalid/expired codes, revoked user records and missing Firestore identities
  are never treated as proof of account admission. Audit events contain no
  passwords, reset codes or URLs.
- Client-side code cannot directly change `password_state`. The Admin SDK
  bypasses client Firestore rules; service credentials and IAM must be protected.
- Rate limiting is still dependent on Firebase code throttling for this
  unauthenticated route. Before public rollout, add an external shared
  rate-limit budget and abuse monitoring. Do not rely on an in-memory
  serverless limiter.
- Existing Firebase links handled outside this controlled route do **not**
  move `password_state` to `user_set`; the Owner must generate a new controlled
  link or perform a verified recovery action.
- Complete live Firebase/Firestore emulator tests, OAuth provider smoke,
  account-link collision handling and multi-host integration before merging
  PR #244. Keep production feature flags off.

## Reset-pending isolation and audited repair (sixth PR #244 increment)

Previously the setup/reset endpoint confirmed the new Firebase password **before**
blocking password-based admission in Firestore. A crash or Firestore outage
between provider confirmation and durable state transition could leave
previous signed sessions or initial-password policy in an ambiguous state.

The revised server-side reset sequence is:

1. Firebase validates the one-time OOB code (without consuming it).
2. Server resolves the trusted Firebase UID and validates durable admission.
3. **Firestore transaction** rechecks the UID/status and sets
   `password_state=reset_pending`, recording `password_reset_started` in the
   same transaction. `reset_pending` is already denied by both Next.js and
   FastAPI identity admission; this is a safety boundary, not a grant.
4. Firebase confirms the new password (consumes the OOB code).
5. Firebase refresh tokens are revoked so old sessions cannot survive the
   password change.
6. A second Firestore transaction requires `reset_pending` and an eligible
   UID/status before switching to `user_set` and writing a completion audit.

If steps 4–6 fail or the process crashes, the account deliberately stays
`reset_pending` and **password admission remains blocked**. An expired code does
not automatically reset the state. This trades availability for a clearly
defined fail-closed security outcome and avoids guessing which credentials
were accepted by Firebase. Linked OAuth may remain usable for an active UID;
all project grants still require RBAC in PR 3.

### Operator repair procedure (development project only until live verification)

1. Review the exact UID and Firebase/Firestore state. Do not infer UID from a
   matching email and never mark a user as `user_set` to work around an error.
2. The Owner explicitly runs the local CLI in a restricted environment:

   ```powershell
   Push-Location backend
   uv run python -m scripts.repair_lab_password_reset --uid <firebase-uid> --project-id <dev-firebase-project-id>
   # Only after reviewing the target and enabling the provisioning operator gate:
   uv run python -m scripts.repair_lab_password_reset --uid <firebase-uid> --project-id <dev-firebase-project-id> --apply
   Pop-Location
   ```

   `--apply` additionally requires `PORTFOLIO_LAB_PROVISIONING_ENABLED=true`,
   a configured pinned `PORTFOLIO_LAB_OWNER_UID` and matching `FIREBASE_PROJECT_ID`.
   The service account is a privileged operator credential; access to it must
   be independently restricted. The CLI gate is **not** a substitute for IAM.

3. The CLI revokes Firebase refresh tokens before a transaction that rechecks
   `reset_pending`, writes `password_state=none`, removes
   `password_reset_started_at_ms` and creates an Owner audit event. It never
   sets `user_set`, sends mail, enables a disabled user, changes grants or
   revives a revoked account.
4. Generate a **new** Owner-controlled password setup link using
   `scripts.generate_lab_setup_link` and deliver it privately. The recipient
   redeems that new code. Existing `none` users cannot enter using a password.

The code is unit-tested with offline fakes. It is **not yet tested against a live
Firebase project** and must not be enabled in production without that test.
Concurrency / ambiguous response and serverless interruption scenarios need
integration validation, and the reset action requires abuse-rate controls before
release. Avoid posting reset codes, service-account details or passwords in CI
logs, GitHub or issue trackers.
