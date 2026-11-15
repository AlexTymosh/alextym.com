# PR5 — Recruitment source cohorts (commit 13, second slice)

`GET /api/workforce/analytics/recruitment-sources` reports synthetic applications
by recruitment source, with optional `campaign_id`, `organisation_id`,
`location_id` and `role_id` filtering. `period_start` and `as_of_date` follow
the existing Workforce analytical date contract.

The denominator is **distinct application IDs received in the selected period**,
not requisitions or all stage events. Screening, shortlisting, interviewing,
accepted offers and actual starts are separately recorded as unique applications
observed by the selected cutoff. Repeated stage events are counted only once.

The `application_to_start_percent` field is an **observed-to-date cohort rate**:
recent applicants have had less time to start, so never interpret this as a
completed-cohort success rate. The report returns an empty `rows` array and
`total_applications: 0` if filters match no data; it does not invent a zero
conversion rate. All rows are synthetic. No protected-characteristic breakdown
is returned; server-side suppression remains for commit 15.

This feature is deliberately read-only and preserves the existing independent
Next.js BFF and FastAPI member checks.

## PR5 / commit 14: initial Recruitment Channels UI

The Workforce Intelligence dashboard now renders this same source-cohort report
as a recruitment-channel table. It uses the existing reporting start/end dates
and the current dataset generation/revision, rejecting a mixed-revision set of
parallel API responses. It does not add a browser-side KPI formula.

The vacancy picker remains specific to the candidate funnel, so the channels
panel clearly says that source totals include **all vacancies** when a vacancy
is selected. No protected-characteristic breakdown is present. Subsequent
commit-14 views will add campaign comparison and recruitment drill-through.
