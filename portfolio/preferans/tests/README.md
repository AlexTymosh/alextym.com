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

`test_secure_rooms.py` covers private state codec, room authorization, idempotency/version conflicts, event redaction and per-user hand projections using an in-memory fake. `backend/tests/test_preferans_access.py` covers host feature gating and grant adapter. Integration with the real Auth/Firestore emulators remains an explicit release gate.

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
