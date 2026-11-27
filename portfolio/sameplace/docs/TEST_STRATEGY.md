# Test strategy — foundation and room core

## Commands (repository root unless noted)

- `node --test portfolio/sameplace/tests/freeze.test.mjs`
- `node portfolio/sameplace/tests/check-freeze.mjs`
- `node portfolio/sameplace/tests/check-foundation.mjs`
- After `npm ci` in `frontend`: `node --test portfolio/sameplace/tests/localization.test.mjs`
- From `backend`: `uv sync --locked --extra dev`; `uv run --locked pytest ../portfolio/sameplace/tests`.
- Full repository: `task ci`, or the external candidate's `ci-no-task.py --format --workers 2` when Task is unavailable. Format only SamePlace and changed host Python files; full Ruff checks remain read-only across legacy. The alternate runner mirrors all eight local checks and does not skip Docker, RAG or Playwright. It is not committed to the repository.

The host workflow retains all five jobs. The project job fetches the pinned baseline and runs hygiene/freeze tests. The frontend task runs localization tests and project-local ESLint after npm install, after host lint/dependency linking and before build/E2E. The backend checks include SamePlace, and Docker copies the editable package before frozen sync. The Playwright smoke verifies the disabled route and unmodified global locale; use the local production build with SamePlace off, never a production external BASE_URL.

| Acceptance ID | Foundation evidence required | State at handoff |
|---|---|---|
| T-001 | Disabled backend, no auth lookup; disabled UI; old paths unchanged | Focused mocked HTTP tests; full browser/host CI pending |
| T-062/063 | Russian keys, plural/fallback/pseudo, scoped `lang`, no global changes | Focused translator tests; full UI and later module coverage pending |
| T-069 | Direct Firestore access remains denied | Rules file unchanged; real Emulator negative tests deferred until data exists |
| T-077 | Detect protected edits, deletions, additions, mode changes, rename, index hiding and manifest tampering | Synthetic Git fixture tests; actual pinned inventory checked on install and CI |
| T-078 | All existing application tests remain green | Full checkout CI not run in author environment |
| T-085 | No paid configuration or provider activation | No data/paid code/config introduced; future measured resource gates still pending |

All tests are synthetic or local. Mock authorization tests prove the adapter contract, not Firebase token verification. Existing host tests exercise shared authorization. Full legacy regression, hosted CI, actual quota and device tests must not be marked passed without evidence. Before release test mobile and desktop with real roles, connection loss/restart, hidden data, data integrity and media capacity. Do not use production records or credentials as test fixtures.

## SP02 additions

- `uv run --locked python -m pytest ../portfolio/sameplace/tests/test_sameplace_room_core.py ../portfolio/sameplace/tests/test_sameplace_room_storage.py ../portfolio/sameplace/tests/test_sameplace_room_http.py ../portfolio/sameplace/tests/test_sameplace_room_guards.py ../portfolio/sameplace/tests/test_sameplace_room_host.py` from backend. Test service invariants, concurrent final-slot, scope/negative access, invite replay/expiry/revoke, transfer, archive/restore, request validation, actual HTTP composition. MemoryStore and fake SDK are isolated tests, not Emulator evidence.
- `test_sameplace_room_emulator.py` is opt-in: local loopback Firestore Emulator only, unique `demo-sameplace-*` project, anonymous credentials, two competing final room slots. Set `SAMEPLACE_RUN_EMULATOR=1` and `FIRESTORE_EMULATOR_HOST=127.0.0.1:8080` only after launching a local Firestore Emulator. It must never be run against production. Actual Auth Emulator, cross-project guest denial on real host, explicit revoke/session binding, CSRF/BFF, enabled mobile UI and provider logs require staging acceptance.
- Existing translator test also compiles and tests the exact BFF operation whitelist. Existing freeze guard is unchanged. New Playwright disabled-entrypoint test covers root room paths and BFF. Full locked Ruff/build/browser/CI required.

T-002–012: focused service and HTTP coverage; actual Firestore concurrent transactions and live auth still pending. T-013/014: capacity values and Owner-only policy persisted; live admission and distinct-user count are SP03, NOT passed here. T-069–072: unchanged deny-all rules, object permission tests, no-cache and idempotent transaction model; real Emulator and production-safe logging verification pending. T-082: Owner-only policy/approval unit coverage. No claims that full acceptance or release is complete.
