# Public portfolio previews

These static screenshots show the existing application interfaces at 1440 by
900 pixels. They contain synthetic demonstration data only. They do not grant
access to the applications or their APIs.

- `fleet-vor-hub-demo.png`: Fleet Issue Hub, using the authenticated UI regression
  fixture from `frontend/e2e/fleet-hub-authenticated.spec.ts`, with a synthetic
  vehicle and example messages attributed to demonstration teams. No email is sent.
- `workforce-intelligence-light.png`: People Voice published findings in the
  application's light theme, using the project router's prepared `INTERVIEW_SEED`
  report from a disposable SQLite
  database. The report is a seeded demonstration, not evidence of a live AI run.

Captured on 22 November 2026 with Chromium against localhost. Both images show
the current shared black demo bar and **Log Out** label. Browser API requests
used local test fixtures, and the remote font stylesheet was replaced by an
empty local response so the capture uses system fallback fonts without external
network requests. No production session, private profile, employee data,
provider credential or live external API response was used.

The public catalogue describes importing, processing and exporting supported
datasets. These screenshots continue to show synthetic records only; the short
demo-bar disclosure stays **Demo v1.0 · Synthetic data only**.
