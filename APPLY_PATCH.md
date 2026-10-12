# Fleet VOR Hub v1.3.1 — Any-domain email allowance

## Changes

`backend/app/api/vor.py`: allow the exact `*` token inside `VOR_DEMO_ALLOWED_EMAIL_DOMAINS`. All recipients are still taken from the current vehicle’s subscribed contacts configured through Manage; no recipient addresses are accepted in the email POST body. Existing exact recipient/domain checks, authenticated session and 15/day quota still work.

`backend/tests/test_vor_v1_3.py`: regression tests for mixed-domain delivery, daily quota and ensuring that `*.example` is not treated as unrestricted.

`backend/vor-demo.env.example` documents `*`. `SESSION_NOTES.md` updated.

## Install (from repo root, Windows PowerShell)

1. Stay on the existing `feat/fleet-vor-hub-demo` branch.
2. Stop backend (`Ctrl+C`).
3. Extract this ZIP into repo root, merging `backend/` and overwriting `SESSION_NOTES.md`. Do not delete `backend/_local/vor_hub.sqlite3`.
4. In Render > backend service > Environment set `VOR_DEMO_ALLOWED_EMAIL_DOMAINS` to the exact value `*` (no quotes).
5. Ensure `VOR_DEMO_SEND_REAL_EMAIL=true`, `VOR_DEMO_EMAIL_LIMIT=15`, and that `RESEND_API_KEY`, verified `VOR_DEMO_FROM_EMAIL` (or `CONTACT_FROM_EMAIL`), and `VOR_DEMO_PUBLIC_URL` are already set. Changing any environment variable may trigger a backend redeploy.
6. Run backend as before: `./scripts/start-vor-backend.ps1` in PowerShell. Refresh the site.

## Notes

- You do not need to enter individual addresses in env. Add or edit subscribed contacts through Manage.
- This patch alone does not enable real sending: it only adds wildcard support to the existing v1.3 live-send pathway.
- A public demo with a guessable password and `*` is open to misuse. Before enabling it publicly, change the password and use Resend account limits; daily recipient cap stays 15 by default.
- Real Resend delivery has not been exercised: tests use a mocked provider.

## Verification

Ran `python -m pytest -q tests/test_vor_demo.py tests/test_vor_v1_update.py tests/test_vor_v1_1.py tests/test_vor_v1_2.py tests/test_vor_v1_3.py` in isolated test environment: 11 tests passed.
