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
