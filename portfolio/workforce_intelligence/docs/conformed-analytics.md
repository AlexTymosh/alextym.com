# PR5 — Conformed analytical core (commit 13, first slice)

This implementation adds project-owned read-only SQLite views; no separate warehouse,
job scheduler, cache or external service is required. They operate on the same
SQLite transaction/revision as Bronze and Silver, so confirmed source edits,
Excel imports and demo reset are visible on the next analytical read.

## Grain and lineage

| View | Grain | Source |
| --- | --- | --- |
| `dim_date` | observed calendar day | `dataset_state` history range |
| `dim_organisation`, `dim_location`, `dim_role`, `dim_pay_band` | reference code | source reference tables |
| `dim_recruitment_source`, `dim_campaign` | reference code/campaign | source reference tables |
| `dim_employee` | synthetic employee ID | `employees`, `employee_profiles` |
| `fact_employment_interval` | substantive employee × intersected effective period | `silver_substantive_employment` |
| `fact_employee_monthly_snapshot` | substantive employee × observed month-end | `fact_employment_interval` and observed dates |
| `fact_vacancy` | approved requisition ID | `bronze_vacancies` |
| `fact_application` | unique application ID | `silver_applications` |
| `fact_application_stage_event` | application × recorded stage event | `silver_application_events` |
| `fact_offer` | offer ID | `silver_offers` |
| `fact_new_starter` | actual starter event / offer ID | `silver_starters` |
| `fact_leaver`, `fact_internal_progression`, `fact_learning`, `fact_pdr`, `fact_probation` | dated operational event | corresponding source event tables |

Monthly snapshots clamp the final, potentially partial month to the dataset's
`as_of_date` and carry `dataset_id`, `dataset_generation`, `source_revision`.
Effective periods are half-open: `[valid_from, valid_to)`.
No view manufactures a missing event or guesses an employee's demographic attributes.
`dim_employee` is an internal analytical source and is **not** a browser API;
server-side small-cohort suppression is planned for commit 15.

## Newly computed KPIs

The canonical server-side `GET /api/workforce/analytics/executive` now includes:

- `offer_to_start_conversion`: accepted-offer cohort in the selected period,
  starts observed by cutoff. Pending accepted offers remain in the denominator.
- `early_attrition_12m`: starters in the selected period with a full 365 days of
  observation by cutoff, and a leaver event within those 365 days.
- `internal_appointment_rate`: internal-marked applications linked to actual
  starters / all actual starters in the period. Missing internal IDs are not
  evidence of external recruitment.
- `retention_rate`: members of the opening substantive workforce still substantive
  at the closing cutoff with no intervening leaver event. **Boundary retention**
  is not proof of uninterrupted work between those dates.
- `new_leavers`: dated leaver events, not inferred contract terminations.
- `internal_progressions`: promotions and internal-appointment events, kept
  separate from recruitment appointments.
- `pdr_completion_rate`, `learning_completion_rate`: completed recorded events
  over all recorded events of the same type in the period. These are **not**
  PDR compliance or population access to learning.
- `probation_pass_rate`: final passes divided by pass/unsuccessful outcomes;
  extensions are unfinished and excluded from the denominator.

Zero denominators and incomplete 365-day follow-up produce typed unavailable
observations (`value: null`), never a misleading zero. Existing KPI metadata
continues to be the authoritative source for tooltips and calculations.

## Deliberately deferred within PR5

This is the **first slice** of commit 13, not completion of the full PR5 scope.
Still required: validated source coverage for the remaining specification KPIs,
explicit campaign/channel segmentation, source-aligned quality rules and tests
for every intended dimension. Commit 14 delivers the dashboard sections and
filtered drill-through. Commit 15 implements confidential small-group
suppression on the server before any protected-characteristic data leaves the API.

No demographic breakdown should be exposed via API until suppression is proven.
Public benchmark values must never be substituted for synthetic computed data.

## PR5 / commit 14: initial Workforce Outcomes dashboard

The existing Workforce Intelligence page now presents all nine outcome KPIs
returned by the canonical executive endpoint, grouped into recruitment and
onboarding, retention and leavers, and progression and development. It reuses
the same server-produced observation, definition, previous comparable period,
dataset revision and quality status as the executive KPI cards. No dashboard
formula or additional endpoint was created.

An October 2026 report cannot show a 365-day early-attrition percentage because
none of its October starters have a full year of follow-up at the October cutoff;
that metric correctly shows **Not available**, not `0%`. Recorded PDR and
learning event completion rates are explicitly not workforce compliance rates.

The sidebar exposes a Workforce outcomes anchor. The emulator browser test checks
its three key representative metrics, including the unavailable cohort state.
Full dimensional drill-through and governed suppression remain later PR5 work.

## PR5 / commit 14: effective-dated monthly trend

`GET /api/workforce/analytics/workforce-trend` returns one observation per calendar
month within the report window. WTE represents a point-in-time snapshot at each
month's last observed date, not the sum of daily WTE. Budget comes from effective
establishment history; substantive WTE comes from the overlap-conformed
employment and assignment intervals. Gap is budget minus substantive WTE.

New starters and leavers count dated events *within the selected month interval*,
clipped to the requested period's first and last days. If the reporting window
starts or ends mid-month, the corresponding point sets `partial_period=true`.
The latest incomplete month uses the requested `as_of_date` (not the dataset's
future month-end). A missing budget produces `null` budget/gap, not zero.

Without an explicit `period_start`, this endpoint reports the complete observed
history (36 months for the controlled full seed, four for the interview seed).
Other executive KPIs retain their existing current-month default. Setting an
explicit date range narrows all analytics, including this trend.

The frontend renders the complete available trend with two WTE series and an
accessible table of the most recent 12 observations. The response inherits the
existing dataset revision, feature-gated transport and data-quality status.
It is read-only, requires no cloud infrastructure and uses no extra packages.
A future drill-through may filter the trend by organisational dimensions;
this first slice shows whole-workforce aggregates only.

## PR5 / commit 14: vacancy ageing and candidate-funnel drill-through

`GET /api/workforce/analytics/vacancy-ageing` counts every effective open
approved requisition at `as_of_date`, not just the paginated vacancy table.
The single authoritative status computation is `vacancy_snapshots`, so a
partial fill remains open until its approved position and WTE requirements
are both met. Administratively closed, cancelled and fully filled requests
are excluded, but closing a requisition never changes substantive WTE.

Age is whole calendar days from vacancy approval, grouped into exactly five
inclusive bands: 0–30, 31–60, 61–90, 91–180 and >180 days. The API publishes
band request counts, remaining approved WTE and a bounded oldest-12 list.
The total request count and remaining WTE reconcile to the same-day canonical
executive open-vacancies and vacancy-WTE metrics. Vacancy request grain is
kept separate from candidate-application grain.

The UI renders the five bands and oldest open requests. Selecting `View funnel`
updates the existing Candidate Funnel filter for that vacancy, including
older requests outside the standard 25-item vacancy page. Data revision
consistency, Firebase/BFF auth boundaries and synthetic disclosure remain
unchanged. No demographics or protected breakdowns are exposed.
