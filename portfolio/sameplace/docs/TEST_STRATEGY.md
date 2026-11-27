# Test strategy — foundation

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
