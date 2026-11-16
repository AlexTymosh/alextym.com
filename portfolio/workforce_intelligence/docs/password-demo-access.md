# Workforce temporary password access (no Firebase dependency)

The Workforce demo now shares the existing **Fleet password value**, not the
Fleet session. The authoritative secret is `VOR_DEMO_PASSWORD` on **Render only**.
The backend issues an eight-hour HMAC-SHA256, purpose-separated Workforce bearer
session on successful login. The Next.js BFF stores it in an `HttpOnly`,
`SameSite=Strict`, secure-on-Vercel, path-scoped cookie. It forwards the token
to FastAPI over the protected `BACKEND_ORIGIN` HTTPS connection. FastAPI verifies
all Workforce data calls, including direct Render calls. The browser never
receives the configured password in a JavaScript-readable configuration.

## Deployment

- Render: set `WORKFORCE_INTELLIGENCE_ENABLED=true` and retain existing Fleet
  `VOR_DEMO_PASSWORD`. Keep `VOR_DEMO_ENABLED` separate.
- Vercel: set `WORKFORCE_INTELLIGENCE_ENABLED=true` and `BACKEND_ORIGIN` to the
  HTTPS Render origin. Workforce checks the HTTPS browser Origin against the
  routed Host on Vercel. The Firebase-specific `PORTFOLIO_LAB_ORIGIN` setting
  does not control Workforce login, logout or writes.
- Do **not** put `VOR_DEMO_PASSWORD` into Vercel, `NEXT_PUBLIC_*`, Git or browser
  source. Do not enable Firebase merely to access Workforce.
- `/portfolio/workforce-intelligence` is the project landing and password form.
- `/portfolio` is a public catalogue for the two portfolio demos.
- `/portfolio/workforce-intelligence/preview` remains the development-only UI
  preview with no API calls or authentication.

## Security limits and verification

The password is shared, so compromise grants access to both Fleet and Workforce.
There is no per-user identity, MFA, audit attribution or immediate per-session
revocation. Rotate `VOR_DEMO_PASSWORD` to revoke issued tokens. Tokens expire in
8 hours. The backend applies a simple per-process login throttle; add an edge WAF
rate limit if the deployment is publicly reachable. Use **synthetic information
only**. Do not use this access scheme with personal, clinical or employment records.

After deployment, verify: missing flag -> 404; wrong password -> 401; login ->
protected data; direct Render data without token -> 401; expired or Fleet token
-> 401; logout removes browser session; read-only and write API operations still
require the same valid Workforce token. Verify `Cache-Control: no-store`, CSRF
Origin rejection on mutations, and session cookie attributes on HTTPS.

All existing Firebase-based Workforce grant documentation and emulator scenarios
are **superseded for this temporary demo**; their code is not deleted from the
wider Portfolio Lab project. They are not prerequisites for this deployment.
