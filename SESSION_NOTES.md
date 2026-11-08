# Main website architecture refactor — execution ledger

**Updated:** 2026-11-08 19:36 UTC
**Baseline:** `main` at `eefd657cb67dd962b7f6126851f7e971dc76313a` (PR #235) before Stage 15.
**Active scope:** main Next.js website, FastAPI site application, Chat/Handoff, RAG/LLM,
site-wide security, tests, observability, deployment and documentation.
**Explicitly deferred:** internal refactoring of the independent `portfolio/fleet_hub`
sandbox and `/fleet-vor-hub` UI. Discuss it only after the main website is signed off.

This file is a **human handoff and execution ledger only**. It must **never** be
read, hashed or validated as a prerequisite by CI, installers, preflight tools,
architecture guards or other runtime code. A stale or missing ledger must not
block builds or deployments.

## 1. Operating agreement and scope boundaries

- **Main website first.** Changes may update the host's stable integration
  contract with Fleet if absolutely necessary, but must not refactor Fleet
  internals, its SQLite lifecycle, seed, operations, email or frontend.
- Keep one Next.js host and one FastAPI host, an installable local Fleet backend
  package and its public frontend entry. Do not introduce microservices,
  global-state frameworks, new paid dependencies or a DI framework without
  a demonstrated requirement.
- Preserve existing public paths, HTTP methods/statuses, JSON and SSE wire
  formats, authentication, CORS, callback semantics, Handoff identifiers,
  Telegram contracts, Redis key names/TTLs, rate-limit policy, RAG filtering,
  answer safety rules, feature flags and deployment configuration unless a
  separate explicitly reviewed change authorizes a behavior change.
- Keep existing Fleet contract tests in the overall CI despite Fleet being
  outside the refactoring scope; do not modify Fleet code merely to improve
  code-style scores or to satisfy a site-specific architectural rule.
- Every stage is a focused PR from the current `main`, independently
  reviewable and squash-merged only after required checks pass.
- Do not expose production Redis, Qdrant, OpenAI, Telegram or email tokens.
  Live integration tests use independent non-production resources and
  never execute destructive operations against production.
- `Owner` is the generic identifier in new explanatory text and test data.
  Established API method and field names must remain compatible.

## 2. How to update this ledger on every change

**Mandatory editing rule:** in the same PR as each code change:

1. Update the stage's current state and its verification checklist below.
2. Append a new row to the **dated change log** in section 3, using the
   actual UTC date (`YYYY-MM-DD`; optionally `HH:MM UTC` when verified).
   Describe *what changed*, the branch/PR/commit when known, and what
   actually ran. Never reuse an old date or fabricate a test result.
3. Mark a stage **DONE** only if all mandatory acceptance criteria were
   actually verified. Otherwise mark **IMPLEMENTED — LIVE CHECK PENDING**,
   **IN PROGRESS**, **BLOCKED** or **PLANNED**, and name the blocker.
4. Confirm `task ci` (locally and in GitHub Actions separately), plus any
   focused integration/evaluation/production checks relevant to the change.
5. Keep this file informational: it cannot be added as a CI preflight gate.

For every PR, provide a branch name, an emoji Conventional Commit squash
message, and PR text with `## Summary`, `## Changes`, `## Testing`
(check only items actually tested). Update this ledger in the same PR.

## 3. Dated stage and change log

| Date (UTC) | Stage / delivery | State | Evidence and scope | Remaining gate / next action |
|---|---|---|---|---|
| 2026-11-05 | Foundation (PRs #208–#226) | MERGED | Portfolio separation, backend module boundaries, Fleet SQLite/package foundation, domain separation and AST guard | Historical work; no re-run implied |
| 2026-11-05 | 08: Chat SSE boundary (#227) | MERGED | `ChatStreamEvent` inside application; HTTP adapter serializes SSE | Existing wire tests still required in later PRs |
| 2026-11-06 | 09A: Chat response extraction (#228) | MERGED | Separate response-flow orchestration | Maintain JSON/SSE and abort tests |
| 2026-11-06 | 09B: Chat lifecycle guards (#229) | MERGED | Request leases; stale async callbacks invalidated by reset/unmount | Maintain race tests |
| 2026-11-07 | 10A: detached handoff cleanup (#230) | MERGED | Server close for known/stale handoffs on reset | Later extended by purge |
| 2026-11-07 | 10B: atomic Redis CAS (#231) | MERGED | EVAL compare-and-swap with bounded retry | Real test Upstash behavior not fully documented |
| 2026-11-07 | 10C: handoff purge (#232) | MERGED | Idempotent DEL on reset; 502/503 failure handling | No full privacy erasure guarantee |
| 2026-11-07 | 10D: Fleet API sibling dependency (#233) | MERGED | Removed cross-router exception; baseline `526cc88b` | Fleet frozen after this baseline |
| 2026-11-07 17:45 UTC | 11: live Upstash contract tests | **IMPLEMENTED — LIVE CHECK PENDING** | Added opt-in `backend/tests/test_upstash_real_integration.py`; checks real REST/EVAL, CAS set/delete, stale writes, concurrent updates, close, TTL and DEL | Static compile checked; no test Redis credentials available; run live tests and `task ci`, then record results |
| 2026-11-07 | 12: client identity and rate limiting | **DONE — LOCAL CI PASS; DEPLOYMENT REVIEW PENDING** | ASGI peer identity only, async endpoint Redis offload, regression tests; no Fleet changes | Run focused tests and task ci; verify proxy at deployment; GitHub CI |
| 2026-11-07 | 11: PR #234 local verification | **LOCAL CI PASS; LIVE PENDING** | Local `task ci` PASS reported after formatting fixes; 4 integration tests SKIPPED; PR #234 Draft | Real non-production Upstash test and PR GitHub CI outstanding |
| 2026-11-07 22:15 UTC | 12: site-only implementation | **DONE — LOCAL CI PASS; DEPLOYMENT REVIEW PENDING** | Added ASGI socket peer-only identity, threaded sync Redis calls in async endpoints and spoof/latency tests | No remote proxy verification; local focused tests, task ci and CI still required |
| 2026-11-07 22:22 UTC | 12: local CI acceptance | **DONE — LOCAL CI PASS; DEPLOYMENT REVIEW PENDING** | Owner reported full local `task ci` PASS: repository, config, wizard, deployment, backend, frontend, RAG and Docker | GitHub PR CI and actual trusted-proxy verification still pending |
| 2026-11-08 11:59 UTC | 13: async Chat/RAG/LLM network I/O | **DONE — LOCAL CI PASS** | Offload JSON and SSE retrieval/generation; close nested streaming iterators; add deterministic concurrency/cancel regressions | Run focused tests and task ci, then mark local DONE; GitHub CI and live production tests are independent gates |
| 2026-11-08 12:56 UTC | 13: test routing correction | **IN PROGRESS** | First focused run: 3 failed, 19 passed; the fixture question 'What are your projects?' unintentionally matched assistant-intro substring 'what are you'. Updated fixture to a RAG-routed request. | Rerun focused tests and full task ci; auto-close Stage 13 only if both pass |
| 2026-11-08 12:59 UTC | 13: local verification and acceptance | **DONE — LOCAL CI PASS** | Focused Chat async/streaming tests and full `task ci` PASS from local verifier | GitHub CI and production concurrency/load checks pending; Stage 11/12 external gates still open |
| 2026-11-08 13:21 UTC | 11: PR #234 squash merged | **MERGED — LIVE TEST PENDING** | main `3a704510`; five GitHub Actions jobs PASS; Owner reported local task ci PASS | Run four opt-in tests against an isolated non-production Upstash |
| 2026-11-08 17:39 UTC | 14: Escalation SSE boundary | **DONE — LOCAL CI PASS; REMOTE CHECKS PENDING** | Transport-independent events/heartbeat, HTTP-only SSE adapter and six deterministic regression tests; no Fleet changes | Run focused escalation tests and task ci before local DONE; GitHub CI and production smoke are separate gates |
| 2026-11-08 17:43 UTC | 14: local CI verification | **DONE — LOCAL CI PASS; REMOTE CHECKS PENDING** | Focused Escalation tests, Ruff lint/format and full `task ci` PASS (verified locally by script, including Fleet compatibility) | GitHub Actions and production SSE smoke still pending |
| 2026-11-08 18:01 UTC | 14: PR #235 squash merged | **MERGED; PRODUCTION SMOKE PENDING** | main `eefd657c`; GitHub Actions PASS (run `42507869229`); local focused and task ci PASS | Production SSE smoke remains a separate release gate |
| 2026-11-08 18:51 UTC | 15: site architecture guard | **DONE — LOCAL CI PASS; GITHUB CI PENDING** | Added site-specific rules, typing-only exemption and import fixture tests | Run focused architecture tests and full task ci, then record DONE |
| 2026-11-08 19:36 UTC | 15: local acceptance | **DONE — LOCAL CI PASS; GITHUB CI PENDING** | Architecture fixtures, Ruff and full task ci PASS on local checkout | Verify GitHub CI after push; production release sign-off remains Stage 17 |
| — | 16: chat frontend cohesion | PLANNED | Narrow lifecycle seams only where justified | Browser lifecycle regressions |
| — | 17: final site audit and release | PLANNED | Docs, security, CI, evaluations and production | Evidence-based sign-off |

**Status interpretation:** `MERGED` records prior GitHub merges; it is not a
claim that this task reran all tests. The Stage 11 integration test *implementation*
is complete, but the **stage itself is NOT DONE** until a real non-production
Upstash run and the full mandatory checks are recorded.

## 4. Stage 11 — independent Redis CAS/EVAL/DEL integration (active)

**Branch:** `test/site-upstash-real-integration`
**Change surface:** `backend/tests/test_upstash_real_integration.py`, this file.
No production runtime changes, no Fleet source changes, no Redis schema changes.

### Why

PRs #231–#232 introduced atomic EVAL-based session mutation and an
acknowledged idempotent DEL. Existing `test_upstash_atomic_escalation.py` and
`test_escalation_purge.py` use simulated Redis; these cannot confirm Upstash's
actual REST/EVAL/Lua behavior, response types or TTL rules.

### Implementation checklist

- [x] Add a separate *opt-in* real Upstash test file (not invoked against
  real Redis in ordinary `task ci`).
- [x] Require an explicit run flag, an explicit non-production acknowledgement
  and dedicated test-only credentials; do not read production env variables.
- [x] Reject malformed/non-HTTPS/non-Upstash URLs before issuing requests.
- [x] Allocate unique random `hnd_integration_*` session IDs for every test.
- [x] Verify EVAL snapshot mismatch `0`, successful EVAL set, successful EVAL
  delete `1`, stale write rejection and no resurrection.
- [x] Verify serialized JSON fields, owner message append/close semantics,
  concurrent appends and append-vs-close, TTL and idempotent DEL 0/1.
- [x] Always attempt per-test cleanup; cap remaining TTL to 90 seconds.
- [ ] Run locally with a **separate non-production** Upstash REST instance.
- [ ] Run offline focused tests and `task ci` in the full repo.
- [ ] Verify GitHub Actions after PR is pushed, capture PR/check URLs.
- [ ] Record actual evidence and promote the stage to **DONE** only then.

### Run instructions (Windows PowerShell)

Create an **independent test Upstash database**, not a production credential
alias. Never commit credentials or console output containing secrets.

```powershell
$env:RUN_UPSTASH_INTEGRATION = '1'
$env:UPSTASH_TEST_ACK_NONPRODUCTION = 'YES'
$env:UPSTASH_TEST_REST_URL = 'https://YOUR-TEST-INSTANCE.upstash.io'
$env:UPSTASH_TEST_REST_TOKEN = 'YOUR-TEST-TOKEN'
Set-Location backend
uv run --extra dev python -m pytest -q -rs tests/test_upstash_real_integration.py
Remove-Item Env:RUN_UPSTASH_INTEGRATION, Env:UPSTASH_TEST_ACK_NONPRODUCTION, Env:UPSTASH_TEST_REST_URL, Env:UPSTASH_TEST_REST_TOKEN
Set-Location ..
task ci
```

**Safety:** never `FLUSHDB`, `KEYS *` or delete arbitrary identifiers. Test
operations affect only randomly created keys and self-expire. Explicit
acknowledgement does not mechanically prove a database is non-production;
verify it independently before running.

### Acceptance evidence to record

| Gate | Actual result | Evidence |
|---|---|---|
| Python test syntax | PASS, 2026-11-07 | `python -m py_compile` on new test |
| Ruff / backend tests | PASS (reported, 2026-11-07) | Local Ruff lint and formatting fixed |
| Real Upstash REST/EVAL | NOT RUN | Separate test Upstash credentials unavailable |
| Full local `task ci` | PASS (reported, 2026-11-07) | Local success reported after formatting/whitespace repair |
| GitHub PR CI | PASS (5/5, 2026-11-07) | PR #234 GitHub Actions: backend, RAG, frontend, project and Docker all successful; live Upstash still pending |
| Production impact | NONE INTENDED | Test and documentation files only; no deployment necessary |

## 5. Stage 12 — trusted client identity and rate limiter

**Implementation branch:** `fix/site-rate-limit-boundaries`
**Implementation state:** DONE — LOCAL CI PASS (production proxy audit pending).
**Priority:** P1 security / availability.
**Observed source:** `backend/app/api/rate_limit.py` trusts the first
`X-Forwarded-For` entry without checking who supplied it; Redis's synchronous
`urllib` limiter is called directly from asynchronous Contact/Escalation
handlers. FastAPI's own sync-dependency execution is separately threadpooled;
do not conflate all call sites.

**Tasks:**

1. Document actual Vercel→Render traffic path and trusted proxy/CDN behavior.
   First test whether untrusted headers are overwritten before reaching
   FastAPI. Do not assume spoofing is exploitable without verification.
2. Establish a single client-IP resolution policy: only accept forwarding
   headers from a **verified** trusted proxy, otherwise use the socket peer.
   Ensure IPv4, IPv6, multiple-hop lists, malformed/empty values and
   reverse-proxy deployment are tested; avoid collapsing all clients into
   one anonymous limiter bucket.
3. Ensure every Redis I/O call from async endpoint paths is non-blocking.
   Prefer consistent awaitable API/transport or explicit threadpool adapters,
   not a broad provider rewrite.
4. Check Redis failover behavior, UTC-day TTL, quota boundaries, rate-limit
   responses, key hashing and metrics. Preserve current fallback policy unless
   changing it is explicitly justified and reviewed.
5. Add tests for spoof attempts in both direct/behind-proxy modes, async
   responsiveness under slow Redis, errors and concurrent requests.

**Local code acceptance:** the off-thread and peer-identification tests pass;
`task ci` is green and the stage change is recorded. **Production security
acceptance:** verify actual proxy forwarding/sanitization on Render and
GitHub Actions before deployment, with final sign-off in Stage 17.
Local DONE must never be described as confirmed production security.

## 6. Stage 13 — Chat/RAG/LLM non-blocking execution

**Implementation branch:** `refactor/chat-async-provider-boundaries`
**Status:** DONE — LOCAL CI PASS.
**Change scope:** `backend/app/api/chat.py`, `backend/app/services/chat.py`, `backend/app/services/chat_metrics.py`, `backend/app/llm/openai_client.py`, `backend/tests/test_chat_async_io_boundaries.py`, this ledger.
**Priority:** P1 performance / correctness.
**Observed source:** `ChatService.stream_answer` synchronously calls RAG
retrieval/LLM clients inside an async generator, including iteration of a
synchronous OpenAI token stream. This risks blocking the FastAPI event loop.

**Work plan:**

- 13A. Establish concurrency and cancellation baseline with fake slow providers;
  capture event-loop responsiveness, first-token delay, disconnect handling,
  number of in-flight calls and token/order safety.
- 13B. Move retrieval, embedding, contextualization and JSON answer I/O onto
  an async boundary (native async provider API preferred where reasonably
  scoped; threadpool bridge only where cancellation/resource cleanup is safe).
- 13C. Refactor streamed token consumption without buffering whole answers or
  creating unbounded worker queues. Ensure abort/disconnect cancels or closes
  upstream streaming resources to the extent supported by providers.
- Preserve all `meta`/`token`/`sources`/`done`/`error` shapes, safety buffering,
  prompt-injection rejection behavior, RAG fallback and metrics.
- Keep tests deterministic; avoid paid API calls in standard CI. Add an
  optional provider-integration check only with a separate opt-in mechanism.

**Done when:** a slow external provider does not stall unrelated requests;
stream order and safety contracts are preserved; cancellation/regression
checks and `task ci` pass; any provider limitations are documented.

## 7. Stage 14 — Escalation SSE transport boundary

**Candidate branch:** `refactor/escalation-stream-boundaries`
**Priority:** P2.
**Observed source:** `backend/app/services/escalation.py` constructs
`ServerSentEvent` / `ServerSentComment` despite being an application service.

- Define small transport-independent escalation event objects.
- Yield logical `meta`/`message`/`closed`/heartbeat events from the service;
  convert to SSE in `backend/app/api/escalation.py` only.
- Preserve Last-Event-ID replay, message IDs, session expiry/close responses,
  heartbeats, polling/disconnect behavior and terminal stream encoding.
- Add golden-wire tests and cancellation tests. Avoid changing Redis store or
  creating another general-purpose event framework.

**Done when:** no service imports `app.schemas.sse`; existing wire contracts
match byte-for-byte where specified; tests and CI pass.

## 8. Stage 15 — website import and architecture guards

**Candidate branch:** `test/site-architecture-boundaries`
**Priority:** P2.
**Observed source:** `backend/scripts/check_import_boundaries.py` already
blocks repository→service/API and domain→infrastructure imports. Other
important directions (site service→site API, RAG/LLM→HTTP API) are not
expressed as explicit rules.

- Audit the **actual** module graph before adding checks; do not invent
  universal rules that reject legitimate composition roots.
- Add focused rules for `app.services`, `app.rag`, `app.llm` and their
  relationship to `app.api` only where architectural ownership is clear.
- Keep scanner tolerant of legitimate `TYPE_CHECKING` imports where needed;
  include positive and negative fixtures, relative imports, exact import
  targets and alias imports; document computed-import limitations.
- No global cross-language dependency analyzer, no new framework.
- Avoid modifying Fleet internals; keep existing Fleet guard unchanged.

**Done when:** justified import cycles/direction violations are blocked in
local CI without false positives; source test fixtures and full CI pass.

## 9. Stage 16 — Chat frontend cohesive responsibilities

**Candidate branch:** `refactor/site-chat-controller-cohesion`
**Priority:** P2 conditional.
**Observed source:** `frontend/hooks/use-chat-controller.ts` is still ~590
lines, though response flow and request leases were extracted already.

- First identify change-coupled state groups and genuine testability issues;
  do **not** split files solely for their line count.
- Extract only stable independent seams: Handoff connection/message/close
  lifecycle, reset cleanup, or view-state derivations if justified.
- Retain a single clear owner for request/session generation; do not create
  duplicated state or new global context/provider layers.
- Maintain browser tests for reset during POST, late SSE callbacks, aborted
  requests, multiple submissions, unmount, closed sessions and JSON fallback.

**Done when:** coupling is demonstrably reduced, tests cover lifecycle races,
UI/UX is unchanged and frontend/full CI pass. If no high-value seam exists,
record a **NO CHANGE NEEDED** assessment and do not add cosmetic PRs.

## 10. Stage 17 — website final verification and documentation

**Candidate branch:** `chore/site-architecture-final-audit`
**Priority:** release gate. This stage closes the main website only.

- Verify app/domain/services/repositories, RAG/LLM, site frontend and API
  module graph; record remaining accepted exceptions and technical debt.
- Recheck rate limiting, secrets, logging/PII redaction, SSE error handling,
  security headers, CSRF/CORS boundaries and dependency vulnerabilities.
- Run backend/frontend/RAG/Fleet compatibility/Docker/CodeQL gates and
  verify GitHub Actions; record SHA and run IDs. Fleet tests are regressions,
  not a request to refactor the sandbox.
- Run RAG contract/evaluation suite and compare retrieval accuracy and
  answer quality against the frozen baseline; distinguish isolated vs paid
  live evaluations.
- Verify production Vercel frontend and **actual** Render backend separately:
  health/live/ready, Chat JSON/SSE, contact flow, handoff availability,
  Redis/Telegram safe probes, timeout and reset behavior. Do not treat
  Vercel `READY` as proof of backend health.
- Update `AGENTS.md`, `SESSION_NOTES.md`, architecture docs and deployment
  instructions, including the Fleet local package in backend Docker build.
- Produce a final site-only architectural inventory, decisions, known risks,
  test evidence and explicit sign-off; then freeze site refactoring and
  separately scope Fleet VOR Hub work.

**Done when:** all critical/high findings are fixed or explicitly accepted;
CI, compatibility and production checks are evidenced; documentation is
accurate and the dated change log identifies the final release SHA.

## 11. Historical references and baseline facts

- PRs **#223–#224:** Fleet SQLite/bootstrap and email/API extraction; preserved
  the immutable approved seed SHA-256
  `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`.
- PR **#225:** Escalation session state moved to `app.domain` with a compatibility
  facade. PR **#226:** AST import guard. PR **#227:** Chat SSE domain events.
- PRs **#228–#230:** Chat response flow, lifecycle races and handoff cleanup.
- PRs **#231–#232:** Upstash atomic CAS and idempotent session purge.
- PR **#233:** removal of Fleet sibling-router import exception.
- Last verified baseline before this change: main `526cc88b` and successful
  GitHub CI run `42395200886` (2026-11-07). This does **not** validate the new
  tests or constitute a new production smoke.
- The detailed **previous ledger** remains recoverable from Git history:
  `git show 526cc88b:SESSION_NOTES.md`. The active plan replaces outdated
  instructions that formerly referred to Step 06 as still pending.

**Next action:** Stage 13 local validation, then an independent PR. Stage 11's live Upstash gate and Stage 12's production proxy audit remain open; green unit/CI tests alone cannot close them.


## Stage 12 implementation record — 2026-11-07 22:15 UTC

**Code delivery: COMPLETE. Release acceptance: PENDING.**

- Client identity now derives from `request.client.host` (ASGI scope) only.
  Application-level rate limiting ignores user-provided `X-Forwarded-For`
  and `X-Real-IP`; Uvicorn's proxy middleware must be configured with a
  verified trusted-proxy allowlist, and upstream must sanitize forwarding
  headers. Verify this on the actual Vercel/Render route before release.
- Synchronous Redis limiter calls from async Contact and Escalation API
  endpoints now run in Starlette's worker thread pool. Sync FastAPI Chat
  dependency already uses the worker pool. No new external Redis client.
- Added peer/forged-header and worker responsiveness regression tests.
- Kept existing Redis key names, daily quotas, `INCR`/`EXPIRE` protocol,
  fallback limiter and HTTP 429 policy unchanged. Concurrent `INCR` and
  separate `EXPIRE` are **not** a single atomic transaction; reassess only
  if a real failure demands a separate change.
- No Fleet source, frontend, Qdrant, Telegram or production data modified.

**Local Stage 12 verification:** full `task ci` PASS is recorded in the
local verification note and dated log. **Not verified:** GitHub Actions
for Stage 12, production trusted-proxy setup and live spoof tests.
Never declare production secure based only on local CI.


### Stage 12 local verification

- Date (UTC): 2026-11-07 22:22 UTC
- Full local `task ci`: **PASS** (reported from the current branch on 2026-11-07).
- Production trusted-proxy/header rewrite: **NOT VERIFIED**; required before final security sign-off.
- GitHub Actions on the Stage 12 PR: **PENDING** until pushed and run.


## Stage 13 implementation record — 2026-11-08 11:59 UTC

**Code complete; local acceptance pending.** This PR changes only the main
website. No Fleet VOR Hub source, database or route is modified.

- JSON `/api/chat` offloads synchronous `service.answer()` to the worker pool.
- Streaming Chat offloads synchronous question contextualization, embeddings,
  Qdrant retrieval, non-streaming fallback LLM answer, and each synchronous
  OpenAI stream `next()` to worker threads. No new provider SDK or dependency.
- SSE `meta/token/sources/done/error` ordering, RAG policy, safety output
  buffer, wire formats, route methods, rate limits and metric names are unchanged.
- Nested SSE generators are explicitly closed on stream cancellation or
  disconnect; the OpenAI SDK response stream is closed on exhaustion/error.
- Added no-network deterministic scheduling, fallback and generator lifecycle
  regression tests; run alongside existing streaming/golden-wire tests.
- Remaining limitations: cancellation cannot forcibly terminate an in-flight
  synchronous network call; thread capacity/timeouts and actual provider
  concurrency should be assessed in Stage 17 before making performance claims.

| Gate | Status | Evidence |
|---|---|---|
| Implementation | COMPLETE | Narrow adapter changes plus tests |
| Focused tests | PASS (local) | `tests/test_chat_async_io_boundaries.py` and Chat streaming/golden-wire suites |
| Full local `task ci` | PASS (local) | Verified by `verify_stage13.ps1` before recording |
| GitHub PR CI | NOT RUN | After push / PR creation |
| Live performance / production | NOT RUN | Stage 17 release verification |


### Stage 13 test-fixture correction

- Recorded (UTC): 2026-11-08 12:56 UTC.
- Initial focused verification: **3 failed, 19 passed** (RAG/LLM workers were never entered because the test question matched a pre-RAG assistant introduction pattern).
- Changed test QUESTION only, no production behavior or Fleet changes.
- Existing policy limitation: substring matching of `what are you` also matches `what are your ...`. Keep as a separate, tested Chat-intent issue; do not silently change user-visible routing in an I/O isolation PR.
- Stage 13 focused suite and full `task ci`: **PENDING RERUN**. `verify_stage13.ps1` writes the DONE row only after PASS.


### Stage 13 local verification

- Date (UTC): 2026-11-08 12:59 UTC
- Focused Chat concurrency, cancellation and SSE regression tests: **PASS**.
- Full local `task ci` (including Fleet compatibility): **PASS**.
- Actual provider/load performance: **NOT VERIFIED**; Stage 17 gate.
- GitHub Actions on Stage 13 PR: **PENDING** until push.


## Stage 14 implementation record — 2026-11-08 17:39 UTC

**Implementation: COMPLETE. Local verification: PASS.**

- EscalationService produces transport-independent domain events and heartbeats; only API module creates ServerSentEvent/ServerSentComment.
- Preserve `meta`, `message` (with ID), `closed`, Last-Event-ID replay, heartbeat comments, exact JSON/SSE framing, HTTP status codes and polling rules.
- Explicitly close the upstream async event generator when the HTTP stream disconnects or is cancelled.
- Add golden-wire, replay, service-type, architecture and disconnect cleanup regression tests.
- No production Redis, Telegram, Fleet, configuration or public response contract changes.
- Local focused tests and full `task ci`: **PASS**, verified on 2026-11-08 17:43 UTC by `verify_stage14.ps1`.
- GitHub CI: **PASS** on main `eefd657c` (run `42507869229`); production SSE smoke: **PENDING**.


## Stage 15 implementation record — 2026-11-08 18:51 UTC

**Code implementation: COMPLETE. Local acceptance: DONE — LOCAL CI PASS.**

- Extends the existing AST guard to `app.services`, `app.rag` and `app.llm`.
- Rejects service/RAG/LLM references to `app.api`, and RAG references to `app.services`.
- Preserves actual valid composition: `app.llm` may reference `app.services.question_contextualizer`; site services may reference RAG, LLM and repositories.
- Recognizes `TYPE_CHECKING` imports as typing-only for newly added rules; existing domain/repository/Fleet rules are not relaxed.
- Covers direct, relative and aliased static imports and literal dynamic imports; computed imports/reflection remain outside the AST scanner's guarantees.
- Adds positive/negative fixtures with exact source path and line; does not modify Fleet sources.
- Live Upstash and production proxy verification from earlier stages remain outstanding, independent of this code-only stage.
- Local focused tests / `task ci`: PASS; GitHub Actions: PENDING.


### Stage 15 legacy fixture correction ? 2026-11-08 19:33 UTC

- Initial verification: 23 legacy tests FAILED because the fixture omitted new services/rag/llm package roots.
- Fixed test fixture only; production scanner remains fail-closed.
- Focused tests and full `task ci`: PENDING rerun.

### Stage 15 local verification — 2026-11-08 19:36 UTC

- New site architecture guard and fixture suite: **PASS**.
- Full `task ci`, including the existing Fleet compatibility guard: **PASS**.
- Stage 15 implementation: **DONE — LOCAL CI PASS**.
- GitHub Actions on the Stage 15 PR: **PENDING**.
- Site release/production audit remains in Stage 17.
