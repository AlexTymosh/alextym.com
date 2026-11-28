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


## SP03 candidate gates

- `test_sameplace_social.py`: deterministic clock and MemoryStore tests for capacity race, multi-tab counting, global policy, ticket expiry/replay/origin, epoch fence, meeting grace, no writes on ping, friend privacy and blocking, chat text/idempotency/expiry/cursor/moderation, internal notice consent/dedupe, location accept/decline and no seat, favourites/recent.
- `test_sameplace_social_http.py`: actual ASGI HTTP and WebSocket using synthetic identity and the SP02 fake Firestore transaction adapter; disabled/auth failures, ticket replay, ping/pong with no store operations, fresh reauth, immediate post-commit live revoke, chat revision, redacted invalid payload and shared quota circuit.
- `test_sameplace_social_host.py`: actual main host mount smoke via HTTP (not internal APIRoute list). `test_sameplace_social_emulator.py`: opt-in local Firestore Emulator only, random demo project, no live service. Existing SP02 and SP01 regressions retained.
- Existing CI-wired `localization.test.mjs` extended with exact allowlist/method checks and 0–10 placement constraints. Browser disabled-route smoke extended; enabled full multi-client and mobile usability are not claimed by that smoke. Full locked typecheck, ESLint, Next build, Playwright, RAG, Docker, Ruff and original freeze checks required.
- Manual acceptance (local demo only): owner plus two guests, duplicate tabs and capacity wait; move room without gaining a seat; decline stays; watch separately; archive/revoke while connected; simulate process restart and quota cooldown; refresh chat and history; disable privacy and verify another-room friend receives no hidden fields; send internal notice and confirm recipient inbox, external stubs produce no external effect. Inspect browser network for no idle HTTP heartbeat or polling; verify direct WSS exact origin and provider frame size/cap, mobile landscape and portrait. Follow RESOURCE_BUDGET soak gates before activation.
- Author evidence and not-run gates are recorded in SESSION_NOTES. Do not mark full CI, Emulator, actual hosted/real-device checks or free capacity as passed without evidence.

## SP04 test gates

New `test_sameplace_decor.py` verifies catalogue, bounds, authorization, no read mutation, conflicts, receipts, cross-room private templates and music scope/epoch/skin independence. `test_sameplace_decor_http.py` uses the real project composition, synthetic credentials and transaction double, asserting 401/403/404/422, private responses, WS revision invalidation and fresh guest view. Existing `localization.test.mjs` adds exact BFF operations, pure audio timing, binary WAV and catalogue labels. Run full no-Task CI; optional real local Firebase Emulator test from SP02/SP03 remains open. Before release perform two-browser designer conflict, library reuse, mobile/touch drag and undo, each scene/skin visual inspection, audio autoplay denial and retry, source switch and room exit, reconnect and real station availability/rights. Real game switching is a SP05/06 gate, not verified by these tests. Full ESLint, locked FastAPI, Ruff, Next production build, Docker and browser tests remain required.
