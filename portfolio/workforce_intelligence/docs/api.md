# Workforce data core API

FastAPI exposes these operations under `/api/workforce`. The browser uses the
same operation paths under `/portfolio/workforce-intelligence/api`. The host
checks membership on both paths. The browser adapter also checks the Origin for
writes and forwards a server-read Firebase session only to `BACKEND_ORIGIN`.
Protected responses use `Cache-Control: no-store`.

| Method and path suffix | Data or behaviour |
| --- | --- |
| `GET /status` | Protected transport probe. |
| `GET /demo/status` | Creates the controlled fixture on first authorised use and returns its current version and dates. |
| `GET /employees` | Point-in-time employment directory ordered by explicit featured metadata. |
| `GET /employees/{employee_id}` | Synthetic profile, current employment status on the requested date and the latest 200 contract and assignment intervals. |
| `GET /operations/{section}` | Paginated management records: vacancies (including drafts), candidates, offers, starters, learning, leavers, references and audit. |
| `GET /operations/establishment` | Available establishment line codes and approved capacity. |
| `POST /operations` | Validated employment, reference and recruitment commands. OpenAPI describes each shape under the `command.action` discriminator. |
| `GET /import/template` | Download the versioned synthetic XLSX template. |
| `POST /import/validate` | Upload a binary XLSX as `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`. Returns a scoped batch ID, expiry, row diagnostics and projected impact. |
| `POST /import/commit` | Confirm `batch_id` with `confirmed: true`, `dataset_id` and `dataset_generation`. Replays an already committed batch. |
| `GET /import/{batch_id}/errors` | Download the originator's row diagnostics workbook. |
| `POST /export` | Download `analytics`, `metrics`, `quality` or `survey` XLSX. Date and vacancy scopes are documented in the [workbook guide](workbooks.md). |
| `GET /vacancies`, `GET /analytics/vacancy-lifecycle` | Point-in-time vacancy list and count by status. |
| `GET /analytics/executive` | Executive metrics, comparator, calculation components and data-quality checks. |
| `GET /analytics/candidate-funnel` | Sequential application cohort, stage counts, conversions and median step durations. Optional `vacancy_id`. |
| `GET /metrics`, `GET /data-quality` | Canonical metric definitions and diagnostics for the implemented projections. |
| `GET /surveys/reports/rota-pressure` | The controlled People Voice report with published evidence, draft status and its linked management action. |
| `POST /insight-pilot/query` | Uses the executive vacancy-rate calculation for `intent: "explain_vacancy_rate"` and optional `as_of_date` and `period_start`. |
| `PATCH /employees/{employee_id}/contracts` | Apply `contracted_fte` at `effective_from`. The MVP supports one effective contract per employee on a given date. |
| `POST /vacancies/{vacancy_id}/cancel` | Close the remaining request with `cancelled_on`. Prior starts remain in the lifecycle. |
| `POST /starters` | Record `offer_id`, `started_on` and `contracted_fte` and create effective employment. Returns `201` and the new employee ID. |
| `POST /demo/reset` | Restore the baseline for all Members. Requires `confirmed: true` and a client-generated UUID `idempotency_key`. |
| `POST /demo/seed` | Replace the shared dataset with the full 36-month fixture. Same confirmation and idempotency contract as reset, with `mode: "controlled"` or `"exploratory"` and optional exploratory `generation_seed`. |

Pass `as_of_date` as an ISO date for historical reports. Executive and funnel
reports also take `period_start`. The default is the first observed day of the
selected month through the selected date. Directory and vacancy requests accept
`limit` (1–100, default 25) and `offset`. A populated `next_offset` continues
pagination. Vacancy status counts cover the filtered date regardless of the page.

Every write carries `dataset_id` and `dataset_generation` from the most recent
GET. Record writes also take `record_version` from the employee or vacancy GET.
For `/starters`, `record_version` identifies the vacancy attached to the offer.
Accepted FTE values are positive decimals up to 1.0 with three decimal places.
Each record mutation returns the updated version and dataset state. Request
identity and correlation come from the authenticated host context. The API
does not take an actor UID in the payload.

Source commands require the current dataset `revision` in addition to its
generation and ID. An optional `record_version` also checks the affected
employee, application or vacancy. Source changes advance the revision and
return `insert`, `update` or `unchanged`; unchanged values leave it intact.
Management lists accept the same `limit` and `offset` as the directory. Employee
profiles contain no demographic categories or raw identity identifiers.

Use `409` to trigger a fresh read after a stale version or writer conflict.
Business or schema validation failures use `422`. Reset cooldown uses `429`
with `Retry-After`. Unavailable storage or authorization dependencies use `503`.
A retry of a successful reset with the same Member, input generation and UUID
returns `replayed: true`, the original `reset_generation` and the current dataset
state. On a new runtime file, the dataset UUID changes and stale writes fail.
The FastAPI OpenAPI document contains the request and response schema.
