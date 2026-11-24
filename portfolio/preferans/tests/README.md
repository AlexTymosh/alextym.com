# Preferans tests

PR 1 introduced the dependency-free static foundation check. PR 2 adds deterministic Python domain tests and randomized legal full-deal sequences. Future PRs add settlement golden fixtures, authorization/emulator tests and three-browser E2E tests.

From the repository root:

```powershell
node portfolio/preferans/tests/check-foundation.mjs
Push-Location backend
uv run python -m pytest ../portfolio/preferans/tests -q
Pop-Location
```

The domain's `conftest.py` temporarily supplies a test-only source path until PR 4 installs the backend package. Do not add a second authentication mechanism or public routes to make tests run.

## PR 4 tests

`test_secure_rooms.py` covers private state codec, room authorization, idempotency/version conflicts, event redaction and per-user hand projections using an in-memory fake. `backend/tests/test_preferans_access.py` covers host feature gating and grant adapter. Real SDK/emulator regression coverage is described below; full three-client UAT remains a release gate.

## PR 5 UI/API contract tests

`test_game_ui_contract.py` validates public invitation envelopes and player-specific
control hints. `frontend/e2e/preferans-ui.ru.spec.ts` validates UI action guards,
immutable hand sorting and the public response contract. Live three-browser
Firebase emulator UAT is still mandatory: `docs/PR05_UAT.ru.md`.


## PR 6 accounting/control tests

`test_game_controls.py` tests undo of the last bid/card, rejection and vote timeout, duplicate counter, 180-second boundaries, two-period penalties, disconnection pause/rejoin, numerically bounded presets, admin compensation, finalized-game immutability, audit redaction and private snapshots with a fake Firestore and injected server clock. `frontend/e2e/preferans-controls.ru.spec.ts` tests the client action guard for pauses and undo votes. Full Firebase emulator and 3-client UAT are required before production (`docs/PR06_UAT.ru.md`).


## PR 7 immutable history and ranking tests

`test_history_ranking.py` covers competition ranks, two golds, triple tie, sheet-discard rules in pure functions, unknown duration, no Firebase UID leakage, single transactional result, idempotent replay, repeated-game aggregates and bounded history. `frontend/e2e/preferans-history.ru.spec.ts` tests sort and timeline order. Firebase Emulator integration and three-browser UAT remain mandatory. `docs/PR07_UAT.ru.md` contains acceptance criteria.

## PR 8 media and recording-consent tests

`test_media.py` covers member-only access, recipient-scoped signalling, idempotency, SDP/ICE bounds, three explicit recording consents, voting denial, revocation and stale media presence with a fake Firestore transaction. `frontend/e2e/preferans-media.ru.spec.ts` validates the allowlisted media contract. These are **not** real-device/WebRTC/emulator tests; required UAT is `docs/PR08_UAT.ru.md`.

## PR 9 release candidate tests

`test_release_security.py` validates seat-bound signalling, cross-room isolation, expiry/secret minimization and rejection of invalid payloads. `test_cleanup_media.py` checks that the operator's maintenance process remains bounded and defaults to dry-run. Updated `test_media.py` verifies UTC expiration metadata, stopped projections after expired presence and a recovered sequence cursor after media/current deletion. Updated `frontend/e2e/preferans-media.ru.spec.ts` tests the pure fail-closed client guard. Real Firestore/Chrome/iOS verification remains a separate acceptance gate.

## HTTP 503 regression and real SDK emulators

The Fake returns a generator from `Transaction.get()` and one snapshot from
`DocumentReference.get(transaction=...)`, disallows reads after writes, applies
create preconditions at commit and rejects a failed batch atomically. Queries
exclude child collections and missing ordering fields. It does not emulate IAM
or concurrency scheduling. `test_storage_diagnostics.py` checks generic HTTP
503 responses and allowlisted logs without exception text, tokens or cards.

`backend/tests/test_preferans_firestore_emulators.py` uses the real Admin SDK,
the real host guard and Auth/Firestore Emulator without dependency overrides.
It covers ID tokens/session cookies, 201 create/replay, empty history/rankings,
join/start/first action, private views, 401/403, cross-project denial, revocation
and idempotency under bounded transaction contention. It skips unless explicitly
enabled; an invalid demo/loopback configuration fails rather than using production.

From the repository root, start this in a separate terminal:

```powershell
firebase emulators:start --only auth,firestore --project demo-preferans-503 --config infra/firebase/firebase.json
```

In a dedicated test terminal:

```powershell
task backend:sync
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.tmp/uv-cache'
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) '.tmp/backend-venv'
$env:PREFERANS_EMULATOR_TESTS = 'true'
$env:FIREBASE_PROJECT_ID = 'demo-preferans-503'
$env:FIREBASE_AUTH_EMULATOR_HOST = '127.0.0.1:19099'
$env:FIRESTORE_EMULATOR_HOST = '127.0.0.1:18080'
uv run --project backend python -m pytest backend/tests/test_preferans_firestore_emulators.py -q
```

Close the test terminal afterwards. The fixture uses synthetic users, strips
runtime credential environment variables and rejects real project IDs/hosted
runtimes. Emulator success does not establish live IAM permission or production
availability. It may exhaust the SDK's five attempts during concurrent lock
contention: the test explicitly records HTTP 503 and checks the next request
with the same key leaves exactly one room. Sequential replay must return 201.

The [incident runbook](../docs/HTTP_503_FIRESTORE.ru.md) records the separate live
read-only IAM/query evidence and the outstanding operator/deployment checks.
