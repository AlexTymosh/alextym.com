# Preferans backend — deterministic domain engine (PR 2)

`src/preferans/domain/` provides pure immutable state transitions for 32 cards, the complete two-stage auction, widow/discard, defense decisions, ordinary trick play, misere and passouts. It has no network, database, clock, external package or site business-module dependency.

**No production API is mounted in this PR.** The site and other project modules are unchanged. PR 3 adds scoring; PR 4 will separately package/mount an authenticated FastAPI API, add durable Firestore storage and update the host dependency lock and Dockerfile.

Run project tests from the repository root: `cd backend; uv run python -m pytest ../portfolio/preferans/tests -q`.

`GameState` is a privileged server-only object with all private hands, widow and discarded cards. Never return it directly over HTTP or store it in a public Firestore view. See `../docs/DOMAIN_ENGINE.ru.md`.

## PR 4 API

`preferans.router` is the project-owned FastAPI entry. Host mounts it only with `app.security.preferans_access.require_preferans_member` and `PREFERANS_ROOMS_ENABLED=true`; every command checks the room seat and monotonic version in one Firestore transaction. No browser Firestore rules were loosened. Runbook: `../docs/SECURE_ROOMS.ru.md`.
