# Workforce MVP metric catalogue

`GET /api/workforce/metrics` exposes the canonical definitions with formula,
grain, eligibility, dimensions, data owner, refresh rule, quality rule and
interpretation. Each executive observation includes the current value, the
components used in the calculation, the comparison value and direction. The
comparison covers an immediately preceding window of equal length when the
dataset contains that entire period. Snapshot measures use the end of each
window. Report values are synthetic.

| Code | MVP definition |
| --- | --- |
| `open_vacancies` | Count of approved, advertised or partially filled requests at the cutoff. |
| `vacancy_wte` | Remaining approved WTE for those open requests. |
| `vacancy_rate` | Open vacancy WTE divided by budgeted establishment WTE. |
| `budgeted_wte`, `substantive_wte` | Effective approved budget and substantive contract WTE with an active assignment. |
| `workforce_gap_wte` | Budget WTE minus effective substantive WTE. |
| `new_starters` | Actual start events dated in the selected window. |
| `median_time_to_hire` | Median days from approval to offer acceptance for acceptances in the selected window. |
| `offer_acceptance_rate` | Acceptances by cutoff in the offer-made cohort divided by valid offers made in that window. Employer withdrawals by cutoff are excluded. |
| `stage_conversion`, `application_to_start` | Distinct applications reaching the later stage divided by the preceding stage or receipt cohort respectively. |

A candidate must reach each preceding stage in order. A repeated event can
supply an eligible reach once. Step duration is the median elapsed time among
applications with both valid dates. A zero denominator or no completed interval
returns `status: unavailable` with a reason. A funnel conversion is also
unavailable when every eligible application reached the prior stage on the
cutoff day and none advanced by that date. Cohort rates describe observed
progress by cutoff and may change as pending records progress.

In the October fixture, three open requests account for 3.0 open WTE against
21.0 budget WTE, which yields 14.29% vacancy rate. One of three valid offers was
accepted by the cutoff, which yields 33.33%. The single October starter entered
the funnel in September. The October application cohort has five applications
and zero actual starts before the guided `offer-002` start is recorded.

## PR5 / commit 13: additional governed outcomes

This catalogue remains the single source of KPI definitions for the API.
All new observations use the shared report window and `status: unavailable`
when their eligible denominator is zero.

| Metric code | Grain and eligibility |
| --- | --- |
| `offer_to_start_conversion` | Accepted-offer cohort; starts observed by selected cutoff. |
| `early_attrition_12m` | Actual starters with 365 days' full observation; dated leaver event within follow-up. |
| `internal_appointment_rate` | Actual starters whose source application has a known internal employee ID. |
| `retention_rate` | Substantive employee cohort present at both reporting boundaries, without a leaver event. |
| `new_leavers` | Dated leaver event count, not inferred contract expiry. |
| `internal_progressions` | Recorded promotion and internal appointment events, not new recruits. |
| `pdr_completion_rate` | Completed recorded PDR events divided by recorded PDR events. Not population compliance. |
| `learning_completion_rate` | Completed learning events divided by recorded learning events. Not workforce training access. |
| `probation_pass_rate` | Final passed decisions divided by final passed or unsuccessful decisions; excludes extensions. |

These are synthetic counts and **not** real NHS or employer performance.
The scope is an initial analytical slice of commit 13; further metric coverage,
segment filters and server-side suppression remain in PR5. See
[conformed model and assumptions](conformed-analytics.md).
