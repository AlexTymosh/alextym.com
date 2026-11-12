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

## Security integration gates still outstanding

This is **not** an admission/RBAC release. Before PR 2 is ready for merge, implement and test the remaining identity requirements:

- Secure invitation and identity-claim process for users other than Owner, not simply trusting a matching email.
- Initial password validity from 1 to 90 days, with server enforcement that cannot be bypassed by immediately exchanging a password-derived ID token for a long-lived session. The credential type and password age must be verified against trusted metadata; no native Firebase expiry is assumed.
- Password-setup links and recovery with non-Owner users; no separate email-verification step, but proof of mailbox ownership through setup link where needed.
- Real-provider tests for Microsoft, Google, GitHub, linking accounts with different emails, existing-credential collisions and corporate tenant restrictions.
- Session revocation, token expiry, CSRF/Origin checks, backend direct-origin verification, and sign-out behavior.
- A policy for browser Firebase Auth persistence vs. server cookie: this increment uses browser-session persistence; new tabs may require re-sign-in for direct FastAPI bearer calls until a finished BFF/token-transport design is implemented.

**Do not turn on the new Fleet authorization or send real project emails under this temporary Owner-only identity probe.** PR 3 owns Firestore-backed grants, and PR 5/6 own Fleet migration and live mail controls.
