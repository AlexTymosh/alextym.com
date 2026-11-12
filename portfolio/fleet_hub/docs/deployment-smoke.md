# Fleet VOR Hub — post-merge deployment smoke checklist

The architecture remains **one Next.js host (Vercel)** and **one FastAPI host
(Render)**. This is a manual validation guide, **not** evidence of a deployment.
Do not paste a demo password, authentication cookie, API keys or private vehicle
data into GitHub issues, logs or CI artefacts.

## Credential-free checks after deployment

1. `https://alextym.com/` returns HTTP 200 and renders the website Home.
2. `/resume`, `/chat`, `/contact` still render; site navigation works.
3. `/fleet-vor-hub` returns 200, contains `noindex`, and displays the access
   screen when tested without cookies. Its three child paths redirect back to it.
4. A clean request to `/api/vor/session` reports enabled state and
   `authenticated: false`, or explicitly reports disabled when the demo is off.
5. A clean request to `/api/vor/bootstrap` cannot return fleet data without a
   valid session (expected 401 when demo enabled; 403 when disabled, according
   to the server's actual configuration). **Do not loosen access checks.**
6. Confirm the Vercel frontend can reach the existing Render backend through
   its current `/api/*` rewrite. Cold starts can affect first response time.
7. If the demo is enabled, manually log in using the existing authorized
   credential through the browser, view a vehicle and log out. Never include
   that credential in scripts or screenshots.
8. Verify the hidden catalogue is still unpublished and the site sitemap does
   not list `/fleet-vor-hub` or `/portfolio` unintentionally.
9. Review relevant Vercel / Render logs for new errors, without exposing secrets.

## Safety / non-goals

- Do not reset, overwrite, or reseed existing production SQLite. The approved
  seed SHA-256 is `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`.
- The `VOR_DEMO_DB_PATH` setting and `/app/_local/vor_hub.sqlite3` default must
  not be altered by the architecture PR.
- No new infrastructure, no paid tier, and no real notification emails in tests.
- Capture actual result/date per item before marking this checklist complete.
