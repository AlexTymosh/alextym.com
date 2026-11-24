# Preferans backend — deterministic domain and protected room API

`src/preferans/domain/` provides pure immutable state transitions for 32 cards, the complete two-stage auction, widow/discard, defense decisions, ordinary trick play, misere and passouts. It has no network, database, clock, external package or site business-module dependency.

The shared FastAPI host mounts `preferans.router` behind Firebase identity and
per-project grants. Rooms require both `PORTFOLIO_LAB_ENABLED=true` and
`PREFERANS_ROOMS_ENABLED=true`; persistence uses the existing server-only
Firestore database. Fleet and Workforce keep their independent modules.

Run project tests from the repository root: `cd backend; uv run python -m pytest ../portfolio/preferans/tests -q`.

`GameState` is a privileged server-only object with all private hands, widow and discarded cards. Never return it directly over HTTP or store it in a public Firestore view. See `../docs/DOMAIN_ENGINE.ru.md`.

## PR 4 API

`preferans.router` is the project-owned FastAPI entry. Host mounts it only with `app.security.preferans_access.require_preferans_member` and `PREFERANS_ROOMS_ENABLED=true`; every command checks the room seat and monotonic version in one Firestore transaction. No browser Firestore rules were loosened. Runbook: `../docs/SECURE_ROOMS.ru.md`.

## Firestore runtime requirements and HTTP 503

The Render credential needs document get/list/create/update and
`datastore.databases.get` for transactions, in addition to its existing Auth
permission. No new database, client access or paid TTL is required.
Single-document transactional reads use `DocumentReference.get(transaction=...)`;
Python `Transaction.get()` returns an iterator.

Storage failures log only operation, stage, exception class/cause class and
host request ID. They do not log exception text, credentials, user identifiers,
request bodies or private cards. See the
[incident diagnosis and operator steps](../docs/HTTP_503_FIRESTORE.ru.md) and
[test commands](../tests/README.md). The patch does not change live IAM or
constitute production multiplayer release sign-off.
