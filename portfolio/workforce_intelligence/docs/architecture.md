# Workforce persistence

The shared FastAPI host mounts the Workforce public router. Workforce owns its
SQLite storage and opens it on the first protected data request. A database or
seed failure stays on the Workforce request path.

| Environment | Default runtime path |
| --- | --- |
| `task backend:dev` from the repository | `backend/.tmp/workforce/workforce.sqlite3` |
| Existing Render container | `/app/.tmp/workforce/workforce.sqlite3` |

Paths are relative to the backend working directory. This is disposable synthetic
state on the existing filesystem. The SQLite application marker prevents Workforce
migrations and resets from adopting another project's database. Workforce uses
the [password demo session](password-demo-access.md) at the shared host.

Each operation uses its own connection with foreign keys enabled. Schema migration
history is recorded in `schema_migrations`. Initial seed, each migration run, and
each reset use transactions. `BEGIN IMMEDIATE` serializes writers across threads
and processes. Readers see a committed snapshot. Unsupported schemas fail closed.
If a migration fails, the previous schema and data survive. To roll back a release
with a newer schema, stop the Workforce service path and regenerate only its
disposable database with the previous code.

The dataset has a UUID for the current database incarnation, a numeric generation
that increments on reset, and a revision that increments on material edits. A
new file gets a new UUID even though it begins at generation 1. Writes compare the
expected UUID and generation under the writer lock. Record revisions also prevent
two sessions overwriting the same record from separate tabs.

Effective periods use dates with inclusive `valid_from` and exclusive `valid_to`.
An open-ended row has a null `valid_to`. A historical query selects the applicable
row on its chosen date. Contracts and assignments each allow one applicable row
per employee in the MVP. FTE is stored as integer thousandths. An effective-date
change splits the applicable interval and retains earlier dates. A correction at
the start of an existing interval keeps the previous value in the mutation audit.

Reset serializes with edits and replaces the synthetic source tables in one
transaction. It keeps reset receipts and records a fresh audit event. Retrying a
successful reset with the same demo actor and idempotency key returns the receipt.
Replacement with a full or exploratory fixture uses the same lock, confirmation
and receipts. New replacements have a 15-second project-wide cooldown. The audit's demo session ID
identifies the shared dataset generation. Audit entries contain the operation,
correlation ID and shared demo actor.

## Analytical projections

Migration 2 adds SQLite views. Bronze views project each operational source at
its original grain with the dataset UUID, generation and source revision. They
reflect the committed snapshot read by the report. Dated source rows and audit
diffs retain the underlying history. Silver intersects employment contracts and
assignments, validates joins between applications, offers, and actual starts, and
combines their dated stage events. Gold computes the executive and funnel
products over these views in one read transaction. A successful mutation is
visible on the next query without a scheduled refresh job.

Quality diagnostics compare Bronze and Silver at the cutoff and flag excluded
applications, offers, starts and unassigned contracts. They describe the rules
implemented in this stage. The API returns the data revision and quality status
together so the dashboard can surface those findings at the point of use.

## Controlled People Voice evidence

Migration 3 adds a synthetic survey, dated responses, analysis, evidence links,
review records and a management action. It installs the report into an existing
`interview-core` dataset without replacing employee or recruitment records, adds
a seed audit event and advances the revision. Reset installs the same report at
the next generation.

`gold_reviewed_survey_findings` requires an approved review that predates
publication and evidence comments from the same campaign. The fixture contains
one published finding and one draft. The audit and UI label the former as a
seeded demonstration review. The report uses a demonstration fallback available
independently of the AI provider. The campaign workflow also collects analyst
decisions and separate publication events.

## Operational history and workbook staging

Migrations 4 and 5 add employment profile status, linked development and
recruitment events, active reference data and recorded dataset replacement
intents. They preserve existing employment and hiring keys. Draft vacancies
are visible in the management view and excluded from the approved-vacancy
projection. Role identifiers remain stable across historical assignments.

Migration 6 adds project-owned workbook batches and rate receipts. An upload is
parsed with bounded archive and sheet limits after both host membership checks.
Preview runs source commands on an in-memory copy of the committed SQLite
snapshot. Confirmation holds the writer lock, verifies the preview's generation
and revision, and commits row changes, audit and the idempotent receipt together.
The report projections read only committed source tables. Authenticated reports
and workbook downloads are never cached by either host.

## Architecture explorer and planning

The Data Architecture workspace reads four live examples at a single dataset
cutoff and revision. The explorer follows one substantive synthetic contract from its
operational row through Bronze and the compatible Silver interval. The Gold
example shows the aggregate establishment, substantive WTE and gap at the same
cutoff. The examples select fixed columns and omit names, survey text and
sensitive attributes. The accompanying checks compare committed source rows
with Silver. The model diagrams show the implemented facts, grain and keys.

The People Voice BPMN covers the campaign, review gate and action lifecycle.
Campaign approval, communication and governance escalation illustrate roles in
the process. The demo records survey, analysis, review, publication and action
state. Teams carry out any communication or escalation outside it.

Migration 10 adds `forecast_runs`, `forecast_results` and `fact_forecast`.
A run is pinned to its input revision and stored idempotently without advancing
the source revision. A reset removes those derived rows and starts a new
generation. [Planning methods](planning.md)

Migration 11 adds a candidate audience to the existing survey settings and
seeds a candidate feedback report where the controlled cohort exists. It
preserves saved campaigns and review history. Candidate surveys use one
synthetic application as their eligible unit. Rating the interview requires a
recorded interview. The report applies the existing suppression and review
rules.

Migration 12 updates the employee directory in place. It gives the first 20
synthetic employees a fixed display order, updates generated aliases, and adds
three non-substantive contracts to the short fixture. The full fixture reuses
existing employee records for its additional featured rows. The migration
retains the dataset ID and employment history and advances the revision so
clients and outstanding workbook previews can detect the change.
