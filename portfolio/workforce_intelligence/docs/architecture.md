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
migrations and resets from adopting another project's database. Firebase identities
and Firestore grants remain in the shared control plane.

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
two Members overwriting the same record from separate tabs.

Effective periods use dates with inclusive `valid_from` and exclusive `valid_to`.
An open-ended row has a null `valid_to`. A historical query selects the applicable
row on its chosen date. Contracts and assignments each allow one applicable row
per employee in the MVP. FTE is stored as integer thousandths. An effective-date
change splits the applicable interval and retains earlier dates. A correction at
the start of an existing interval keeps the previous value in the mutation audit.

Reset serializes with edits and replaces the synthetic source tables in one
transaction. It keeps reset receipts and records a fresh audit event. Retrying a
successful reset with the same Member and idempotency key returns the receipt.
New resets have a 15-second project-wide cooldown. The audit's demo session ID
identifies the shared dataset generation. It contains neither a Firebase credential
nor an individual browser session identifier.

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
