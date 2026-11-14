# Portfolio Lab identity verification

PR [#244](https://github.com/AlexTymosh/alextym.com/pull/244) remains open.
Review the remaining identity release gates below before merging.
This record covers Identity, UID admission and session transport.

## Development environment

| Component | Observed configuration |
| --- | --- |
| Firebase | [Portfolio Lab Dev](https://console.firebase.google.com/project/portfolio-lab-dev/overview), Spark, one Web App, Email/Password enabled |
| Firestore | Standard, `(default)`, `europe-west2`, deny-all client rules equivalent to the committed rules |
| Firebase Auth settings | Email enumeration protection enabled. Create separate accounts for different providers using the same email. The exact Vercel branch alias is an authorized domain. The console confirms a dev project quota of 120 Identity Toolkit queries per minute. |
| Render | [Portfolio Lab dev](https://dashboard.render.com/web/srv-dbrp90rrjlhs73c3p340), Docker Free in Frankfurt, branch `feat/portfolio-firebase-identity`, manual deploys, `/api/health/live` |
| Vercel | [PR branch preview](https://alextym-com-git-feat-portfolio-firebase-identity-alextym.vercel.app), standard Vercel Authentication. Branch-scoped Firebase values, the exact HTTPS application origin, the dev Render origin, and `NODE_OPTIONS=--experimental-require-module`. |
| IAM | Separate custom roles for the two dev runtimes. Render reads Auth user records and Firestore documents. Vercel additionally issues sessions, revokes tokens, and creates or updates Firestore documents in transactions. |

Keep both hosted Lab flags off while provisioning credentials. Set the same
test Owner UID in both environments. Preview and Render use separate runtime
credentials. A local provisioning identity additionally needs
`firebaseauth.users.create` and `firebaseauth.users.sendEmail` for Admin SDK
account creation and link generation. Generating a link with the SDK does not
send email. Keep operator credentials outside the hosts.

Render Free shares build, bandwidth and instance-hour allowances with its
workspace. Verify remaining allowances before deploying or running hosted
tests. No billing account is attached to the Firebase Spark project.
Render's managed OIDC requires a Pro workspace. A dev-only service-account key
is compatible with Free. Store it in the Render secret file and use ADC via
`GOOGLE_APPLICATION_CREDENTIALS`. Use a sensitive branch-specific server
variable on Vercel for its separate key. See
[Render Free](https://render.com/docs/free) and
[Render plan features](https://render.com/docs/platform-features-by-plan).

Vercel disables CommonJS `require(esm)` by default. With the locked Firebase
Admin SDK, loading Auth fails at runtime unless that feature is enabled.
Set `NODE_OPTIONS=--experimental-require-module` only on this Preview branch
and redeploy after the change. The server imports Auth on demand after the
feature gate, so disabled Lab routes do not rely on that option. See
[Vercel Node.js configuration](https://vercel.com/docs/functions/runtimes/node-js/advanced-node-configuration).
Use the project's short-lived development OIDC token to reach its protected
Preview. Scope the token to the preview origin and keep it out of test output.

Register GitHub and Microsoft OAuth applications for the dev project only.
Use Firebase's exact provider callback
`https://portfolio-lab-dev.firebaseapp.com/__/auth/handler`.
Enter the client secrets in Firebase Authentication. Google requires an
approved support email visible on its consent screen. The project administrator
has granted the designated support account only the project's OAuth Config
Editor role; switch to that account in a separate browser profile before
configuring Branding. Keep the OAuth audience in Testing. GitHub registration
requires access to the account's developer settings. The Microsoft account
available during verification could not access an Entra tenant with app
registration rights. Use an existing eligible tenant within the free tier.
See the [GitHub app registration guide](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app),
[Google branding requirements](https://support.google.com/cloud/answer/15544987?hl=en)
and [Microsoft app prerequisites](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).

## Security findings

| Severity | Finding | Current treatment |
| --- | --- | --- |
| High | An expired initial password could still attach a provider through Firebase and create an OAuth session. | Both hosts require an app-approved binding to the exact current Firebase provider subject. Confirmation requires a recent admitted session and reauthentication of the additional provider. |
| High | The default Firebase account policy can attach or replace a provider based on a matching email. | Dev uses separate accounts per provider. Application admission requires the trusted UID and approved provider subject. Validate live collisions for each OAuth provider. [Firebase account behavior](https://firebase.google.com/docs/auth/users) |
| High | Reset redemption used an email to look up the application identity, and completion could match a different pending reset. | Only the latest Owner-issued code digest for the exact UID enters the reset transaction. Completion and Owner repair check that operation. The audit records no code. |
| High | A change between Auth enablement and Firestore activation could overwrite a disabled or changed invitation. | Activation runs in a Firestore transaction and rechecks the original UID, inviter, state and provisioning time. |
| Medium | Firebase revocation timestamps use second precision. | Admission after reset or repair requires authentication in a later second. Both hosts also check the Firebase revocation and disabled-user state. [Firebase session management](https://firebase.google.com/docs/auth/admin/manage-sessions) |
| Medium | An exact Origin check can fail behind an adapter that reconstructs the request URL. | Hosted Next.js uses a configured HTTPS origin. The route rejects an absent or mismatched Origin, even when client-provided forwarding headers match it. |
| Medium | Direct Firebase sign-in and Next.js reset endpoints have different abuse surfaces. | Firebase reports the same error for wrong passwords and unknown emails. Next.js bounds JSON bodies, checks the code tag before Firebase, and returns generic errors. Vercel limits the three auth POST routes on the dev alias to 20 per IP per minute. The separate Firebase dev quota is 120 queries per minute across the project. This project-wide ceiling cannot isolate one abusive client. [Firebase API keys and quotas](https://firebase.google.com/docs/projects/api-keys) |
| Medium | The default Vercel runtime could not load Firebase Admin Auth. | Enabled `require(esm)` for this Preview branch. The Auth module loads only after the Lab feature gate. Verified the hosted session exchange and password reset after redeploy. |
| Medium | Requests sent to an alternate Vercel deployment hostname could evade a preview-alias rate limit. | Lab POST and DELETE require the configured Origin and its actual `Host` on Vercel. The WAF rule can match the exact preview alias and `preview` environment. |

## Evidence and merge gates

| Scope | Result |
| --- | --- |
| Baseline `c13e972` | GitHub Actions passed all five jobs and CodeQL. Vercel Preview reached READY. Local `task ci` passed. |
| Render dev baseline | The `c13e972` deploy reached Live. Liveness returned HTTP 200, and the disabled Lab identity endpoint returned HTTP 404. |
| Security candidate `1689cc2` | [GitHub Actions](https://github.com/AlexTymosh/alextym.com/actions/runs/43620062596) 5/5 and [CodeQL](https://github.com/AlexTymosh/alextym.com/runs/132523662280) passed. Vercel and Render deployed the same commit. Local `task frontend:check` passed (308 Playwright tests) with `require(esm)` disabled. The npm production dependency audit reported zero vulnerabilities. |
| Live Firebase, local application hosts | PASS: signed ID tokens and five-day session cookie; unknown UID denied; initial password reusable before expiry and denied after expiry; valid session passed Next.js BFF to FastAPI. No credential, wrong scheme and forged signature denied on FastAPI. Hostile Origin denied even with spoofed forwarding headers. |
| Live Firebase, provisioning and reset | PASS: Owner-initiated provisioning, no-email private setup link, stale link and wrong UID denied. Two concurrent reset requests returned HTTP 200 and 400; replay denied; Firestore reached `user_set`; the new password worked and the old session was rejected. With an injected `reset_pending` state, password access was denied on both hosts; the repair CLI and a fresh link restored the UID. A disabled Auth user was denied on both hosts. |
| Live Firebase, IAM and rules | PASS: Render role read Auth and Firestore, and Firestore write was denied. Vercel role issued a session and could not generate setup links. Unauthenticated and authenticated client reads and client writes were denied by Firestore. Wrong password and unknown email returned the same `INVALID_LOGIN_CREDENTIALS`. |
| Local hosts with Firebase Emulator Suite | PASS: pinned Owner password and session, independent FastAPI credentials, cookie transport, unknown UID, initial-password setup and expiry, emulated OAuth binding and conflict, private link and replay, concurrent resets, disabled account, repair and reissue, and deny-all rules. The simulated interruption was injected as a Firestore state. |
| Live OAuth | Google Branding requires the designated support account. GitHub OAuth application registration was blocked by browser access approval; the Microsoft account had no suitable Entra tenant. Google, GitHub and Microsoft consent, different-email linking and conflicts with live test accounts remain release gates. Emulator proofs do not satisfy them. |
| Hosted Firebase sessions (`c394e90`, `1689cc2`) | PASS: the pinned test Owner signed in to the protected preview. Vercel issued an invitee a five-day cookie with `Secure`, `HttpOnly`, `SameSite=Strict`, and host-only scope. Render accepted a valid bearer token and the forwarded cookie. Both hosts denied a valid but unknown UID and a forged credential. Vercel denied missing or hostile Origin and rejected a mutation on the alternate deployment hostname. Both hosts denied an expired five-minute test session. Vercel rejected an otherwise valid ID token when authentication was older than five minutes. |
| Hosted recovery (`1689cc2`) | PASS after enabling the WAF and lowering the Firebase quota: two concurrent reset requests returned 200 and 400. Replay, stale link and wrong UID were denied. The new password worked; the old token and session were rejected. An injected `reset_pending` blocked password access on both hosts; repair and reissue restored access. A disabled Firebase user was denied on both hosts. No email was sent. |
| Serverless interruption and abuse | Hosted recovery from an injected interruption passed; the test did not kill a real invocation. PASS: 27 empty POST requests produced 20 application responses and seven WAF `429` responses; a control GET retained its normal `401`. WAF analytics attributed all seven blocks to the dev rule. The fixed window is per Vercel region. |
| Direct Firebase reset provider | PASS: issuing a new code invalidated the earlier provider code, and redeeming the new code invalidated replay. The direct Firebase endpoint can consume a valid code; it cannot set the Lab password state or grant access. |

The two dev runtime certificates expire on 2026-11-21; renew both before
continuing hosted verification after that date. The temporary operator
certificate expires on 2026-11-15. Render also has an unused, older key without
an expiry; the running service uses the new certificate. Confirm retirement
of the old key separately. Store private keys in the hosts' secret stores.

The production login route returned HTTP 404. The branch preview uses standard
Vercel Authentication. The automated tests used its existing project OIDC
policy. The project has no persistent automation bypass key.

Keep PR #244 open until real provider sign-in, linking with different emails,
and collisions are verified. Use only fictional identities for these tests.

## Local emulator reproduction

Install Firebase CLI and Java for the Firestore emulator. From the repository
root, run:

```powershell
firebase emulators:start --config infra/firebase/firebase.json --only auth,firestore --project demo-portfolio-lab
```

Set these process variables in both app shells and in the smoke runner shell:

```powershell
$env:FIREBASE_PROJECT_ID = 'demo-portfolio-lab'
$env:FIREBASE_AUTH_EMULATOR_HOST = '127.0.0.1:19099'
$env:FIRESTORE_EMULATOR_HOST = '127.0.0.1:18080'
$env:PORTFOLIO_LAB_ENABLED = 'true'
$env:PORTFOLIO_LAB_OWNER_UID = 'lab-emulator-owner'
```

Start FastAPI from `backend` on `127.0.0.1:14800` with `ENVIRONMENT=test`.
Start Next.js from `frontend` with these additional values:

```powershell
$env:BACKEND_ORIGIN = 'http://127.0.0.1:14800'
$env:PORTFOLIO_LAB_ORIGIN = 'http://localhost:14300'
$env:NEXT_PUBLIC_FIREBASE_PROJECT_ID = 'demo-portfolio-lab'
$env:NEXT_PUBLIC_FIREBASE_API_KEY = 'demo-portfolio-lab'
$env:NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN = 'demo-portfolio-lab.firebaseapp.com'
$env:NEXT_PUBLIC_FIREBASE_APP_ID = 'demo-app'
$env:NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_URL = 'http://127.0.0.1:19099'
npm run dev -- --hostname 127.0.0.1 --port 14300
```

From `backend` in the smoke shell:

```powershell
$env:PORTFOLIO_LAB_PROVISIONING_ENABLED = 'true'
$env:PORTFOLIO_LAB_ALLOW_LOCAL_HTTP = 'true'
uv run python -m scripts.smoke_lab_identity_emulators
```

The runner writes fictional test data to the emulator and emits outcome labels.
Use a fresh in-memory emulator for a clean run. The Auth emulator verifies flow
and state, while real OAuth provider consent and public-key verification
require a live project. [Firebase Auth emulator](https://firebase.google.com/docs/emulator-suite/connect_auth)
