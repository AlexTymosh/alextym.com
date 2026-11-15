# Workforce MVP source data

The `interview-core` seed uses generation seed `1733`, version `1.1`, and the
observed dates 1 July to 31 October 2026. It contains 15 featured people, two
additional people recruited during the observed period, three synthetic budget
lines, six vacancies, nine applications and six offers. Dates, source IDs and
values are reproducible on a fresh database and after reset. Bootstrap and reset
timestamps record the actual operation time. Separate installation UUIDs identify
separate runtime files.

| Source | Grain and time rule |
| --- | --- |
| `employees` | One synthetic person with a stable ID. Featured people use `is_featured_demo_employee` and ascending `display_order`. |
| `employment_contracts` | One effective interval per employee. FTE is in thousandths. The substantive flag governs establishment calculations. |
| `organisation_assignments` | One effective assignment interval per employee with a budget line key. |
| `establishment_lines`, `establishment_history` | One organisation, location and role combination, with effective-dated budgeted WTE and approved positions. |
| `vacancies` | One recruitment request, with approved position count and WTE, dated approval and advertising, and optional dated administrative closure or cancellation. |
| `candidate_applications` | One application for one vacancy, with receipt date and source. |
| `application_stage_events` | One dated occurrence of screening, shortlisting, interview, completed checks, confirmed start or probation completion. An application can reach a stage repeatedly. |
| `offers` | One conditional offer per application in the MVP. Offer dates and decisions supply their own recruitment stages. |
| `starter_events` | One actual start against an accepted offer. The event preserves the recruited WTE at the start date and links to the effective contract and assignment. |
| `survey_campaigns`, `survey_responses` | One controlled survey and 12 dated synthetic responses. Ten include analysable comments. |
| `ai_analyses`, `ai_signals`, `survey_signal_evidence` | One fallback analysis, two signal records and distinct same-survey response links. |
| `analyst_reviews`, `management_actions` | Separate fixture review and linked proposed action. The confirmed finding qualifies for Gold and its draft counterpart remains unpublished. |

## Controlled scenarios

- `emp-001` starts at 1.0 FTE. Changing it to 0.8 on 20 October increases
  workforce gap by 0.2 from that date. `emp-003` has seeded history across
  a prior 1.0 to 0.6 FTE change.
- `vac-001` has one actual 1.0 FTE starter. `vac-002` was cancelled without a
  starter. `vac-004` has one 0.8 FTE starter against two approved positions and
  1.8 approved WTE.
- `vac-003` has an accepted offer with checks and a confirmed start. The
  actual start event is pending and leaves substantive WTE unchanged.
- `vac-005` was administratively closed with a withdrawn offer. `vac-006`
  is open without a starter and supports the guided cancellation example.
- Application `app-004` has two screening events and counts once at screening.

See the [sources and assumptions register](sources.md) for public context.
