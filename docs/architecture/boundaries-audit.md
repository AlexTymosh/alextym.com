# Architecture boundaries audit — verified 2026-11-02

**Repository:** `AlexTymosh/alextym.com`
**Inspected branch / snapshot:** `main`, `88b24f5d24a7ee69aed0ec6db460af10afa3218c` (latest commit seen 2026-11-02 18:48 UTC)
**Scope:** module ownership, dependency direction, god modules, persistence lifecycle, service/API boundaries, architecture checks, Codex instructions.
**Status:** *repository-file review, not a full local static/dynamic audit.* This document is a refactoring plan; installing it does not implement production code changes.

## Verification and limitations

- Previous local documents `architecture-boundaries-audit-current.md` and `SESSION_NOTES.md`: **read fully**. The *original* 14-issue source report `architecture-boundaries-audit-14-issues.md`: **unavailable**, so its exact 14 assertions could not be revalidated.
- Current repository `main`: **read through connected GitHub**; recent PR metadata #208/#209/#213/#214/#215/#216/#221/#222 checked. The files below were examined in the current branch, with source excerpts and symbol/line checks. This is not proof that every file in the repository was inspected.
- `git clone`, full filesystem-wide dependency graph, automated AST/TypeScript lint, tests and `task ci`: **not run** in this audit environment (local GitHub DNS unavailable). The PR descriptions report prior passes, but those are not new test results.
- Priority is about **architecture risk**, not proven runtime bugs. `confirmed` means directly observed in source; `risk` means the consequence needs tests/reproduction.

## Project topology actually found

```text
alextym.com — one modular monolith / one public website
├─ frontend/                        Next.js host, public routes and shared site
│  ├─ app/fleet-vor-hub/             thin Next route adapters/redirects
│  ├─ components/, hooks/, lib/     site chat and UX
│  └─ e2e/                          Playwright contracts
├─ backend/                         FastAPI host + site/RAG services
│  └─ app/
│     ├─ main.py                    mounts fleet_hub.router exactly once
│     ├─ api/                       HTTP, SSE, site routers
│     ├─ services/                  site use cases / orchestration
│     ├─ repositories/              site persistence adapters
│     ├─ rag/, llm/                 retrieval/provider modules
│     ├─ schemas/                   public transport models
│     └─ core/                      shared configuration / cross-cutting
├─ portfolio/fleet_hub/
│  ├─ frontend/src/                 fleet feature UI, exposed via index.ts
│  ├─ backend/src/fleet_hub/
│  │  ├─ router.py                  public FastAPI router entrypoint
│  │  ├─ api/                       eight Fleet routers
│  │  └─ services/                  SQLite, imports, operations, reporting, mail
│  └─ tests/                        Fleet API/data tests
└─ scripts/                         architecture and CI guards
```

**Preserve:** one Next host and one FastAPI host; `fleet_hub` installable local `uv` package; `@fleet-hub` frontend entry; `/fleet-vor-hub`, redirects, all `/api/vor/*` methods; API/JSON/SSE/auth/cookie/CSRF contracts; Qdrant indexing and RAG semantics; `VOR_DEMO_DB_PATH` and existing runtime DB; immutable seed SHA-256 `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`. No microsvc, broad route-group redesign, new paid infrastructure or database reset. The current Fleet module boundary is a good foundation — refine **inside** it.

## Old audit plan: claim-by-claim revalidation

| Previous issue | Current finding (snapshot) | Disposition |
|---|---|---|
| B1 `ChatService` owns SSE | **Confirmed.** `backend/app/services/chat.py` 640 lines; yields `ServerSentEvent`, constructs `meta/token/sources/done/error` and payloads; `backend/app/api/sse.py` already serializes framing. | Keep, but **P2**, not the first refactor. Separate business streaming decisions from SSE event shape; do not rewrite stream buffering. |
| B2 Handoff patterns in chat | **Confirmed.** `HANDOFF_REQUEST_PATTERNS` and `HANDOFF_CONFIRMATION_PATTERNS` remain in `chat.py` lines ~79–155. | **P3** move alongside policy data when touching chat; no separate PR solely for cosmetic constants. |
| B3 `EscalationService` depends on API DTO and SSE | **Confirmed.** `backend/app/services/escalation.py` imports `app.schemas.escalation` and `app.schemas.sse`, creates/yields transport objects. | **P3/defer**: small application, working thin routers; command/DTO proliferation is not justified without a measured need. Stream/event output can align with B1 later. |
| B4 Repository imports services | **Confirmed.** `backend/app/repositories/upstash_escalation_session_store.py` imports `app.services.escalation_session_state` (record and transitions). | **P1** direct dependency-direction violation. Introduce neutral `app/domain/escalation_session.py` or equivalent and keep old import adapter temporarily if tests depend on it. |
| B5 Frontend controller becomes god hook | **Confirmed.** `frontend/hooks/use-chat-controller.ts` 632 lines, manages AI submit, warmup, handoff, scripted responses, reset and UI state. | **P2** isolate pure state transitions and independent lifecycles first, then split hook. Preserve cancellation and handoff races. |
| B6 ChatShell presentation helpers | **Confirmed.** `frontend/components/chat-shell.tsx` 447 lines, includes `DelayedMessageSources` and formatting helpers. | **P3** optional; keep unless a real UX reason to change. Avoid a one-component-per-file dogma. |
| B7 Documentation drift | **Confirmed; worse than earlier report.** Repo `SESSION_NOTES.md` is 436 lines; top says PR #216 work pending though #216 merged 2026-11-01. `AGENTS.md` 415 lines shows Koyeb deployment and no Fleet topology. `portfolio/fleet_hub/README.md` still describes PR1 foundation despite completed migration. | **P1 prerequisite** to avoid Codex executing stale work. Update and archive history outside active notes; explicitly distinguish recorded vs verified status. |

**Correction to prior plan:** do not run the old eight-commit sequence unchanged. The Fleet architecture and current source deserve higher priority. `frontend/lib/chat-state.ts` is now only a tiny export facade; its original split is not an open task.

## New and current problems, ordered by impact

### A-01 — Fleet email delivery and auth inside API router — P1, confirmed

**Evidence:** `portfolio/fleet_hub/backend/src/fleet_hub/api/vor.py` (454 lines), especially `required`, `same_origin`, `session_valid` and `create_message` (~lines 247–366). Eight Fleet API modules import `required` / `same_origin` from `fleet_hub.api.vor`, coupling sibling routers to a large router. The same endpoint validates recipients, builds email payloads, reads env/config, reserves quota in SQLite, calls `httpx.post` to Resend, marks delivery status, and records an event.

**Risk:** unrelated changes (session/auth, delivery policy, API response, event storage) touch the same handler. **Confirmed execution order:** `httpx.post` to Resend and `finish_email_delivery(..., "accepted")` run *before* `vor_store.add_event(...)`. Therefore an error after provider acceptance can leave delivery and local event state inconsistent (a potential failure path, **not** a reproduced incident). Network side effects and DB changes are non-atomic; failure cases need deterministic tests and an explicit idempotency/reconciliation policy. Do **not** claim email is currently lost or sent incorrectly without reproduction.

**Action:** extract `fleet_hub/api/dependencies.py` (HTTP auth/origin adapters), and a compact `fleet_hub/services/message_delivery.py` (recipient rules, quota, provider adapter and delivery orchestration). Put HTTP-to-service error mapping in API; do not move `Request`, `Response`, `HTTPException` into service. Keep cookie format and failure status behaviour unchanged. Introduce fake sender and tests for quota, provider error, event persistence and replay/race behaviour. Avoid changing email semantics in move-only PR.

### A-02 — Fleet database initialization/migrations on request paths — P1, confirmed structure / runtime risk

**Evidence:** `fleet_hub/services/vor_store.py` (737 lines) owns path/seed creation, SQLite connection, schema/seed migrations, subscribers, bookings, workflow, contacts and email quota; `connection()` invokes `migrate_v1_demo`, `migrate_v1_1_demo`, `migrate_v1_2_demo` in the connection flow. `fleet_hub/services/vor_data.py` (~601 lines) adds `_migrate()` inside `database()`, alongside CSV/XLSX parsing and import transactions. `fleet_hub/services/vor_operations.py` (~601 lines) calls `_setup(db)` from read methods such as `overview()` / `queue()` / `details()`, while also implementing case operations and SQL.

**Risk:** read paths can perform schema/seeding work; migrations and queries share mutable SQLite lifecycle, complicating locking, startup, concurrency and rollback analysis. This does **not** establish a reproduced corruption or performance defect.

**Action, in narrow stages:** (1) snapshot actual migration/seed behaviour and add temporary-db tests (fresh/legacy/repeated initialization/concurrent access); (2) provide one shared SQLite connection/access API, with explicit transaction semantics; (3) move idempotent schema and seed initialization to an explicit bounded bootstrap/migration boundary, preserving runtime DB, approvals and compatibility; (4) split *by use case* (`vehicle_registry`, `import_preview_commit`, `operations`, `contacts`, `notifications`) only after initialization is safe. Never rewrite all SQL or change live DB in one PR.

### A-03 — Missing cross-layer dependency checks inside host/Fleet — P1, confirmed guard gap

**Evidence:** `scripts/check-fleet-backend-boundaries.mjs` (71 lines) enforces file ownership, package metadata, seed hash, host entry and bans `from app.api/services` from Fleet, **not** internal Fleet API-to-API dependencies or site repositories importing services. `scripts/check-website-portfolio-boundaries.mjs` already enforces useful frontend boundaries with import/CSS scanning; preserve it. Existing tests do not prove a universal dependency-direction rule.

**Action:** introduce a focused CI import-graph check, preferably Python AST for backend and existing TypeScript/ESLint tooling for frontend. Define approved dependency rules and assert violations with exact paths; specifically forbid `app.repositories -> app.services`, `fleet_hub.services -> fleet_hub.api`, and `fleet_hub.api.<router> -> fleet_hub.api.<other router>` except the central public composer. Add fixture-based positive/negative tests for guard itself. Keep legitimate service→repository dependencies; do not force a large DI framework. Account for compatibility adapters explicitly.

### A-04 — Documentation and Codex handoff drift — P1, confirmed

**Evidence:** `SESSION_NOTES.md` top still calls #216 unfinished; PR #216 is merged. `AGENTS.md` contains outdated Koyeb/old layout wording, while `docs/architecture/portfolio.md` states Vercel + Render and current host/module boundaries. `portfolio/fleet_hub/README.md` is frozen at PR1 stage. `docs/architecture/portfolio.md` also describes PR5 in prospective form. These are instructions Codex may treat as current truth.

**Action:** replace active `SESSION_NOTES.md` with short task ledger; move historical handoffs to `docs/archive/` only if worth preserving (Git history already exists); correct `AGENTS.md` topology, hosting and documentation pointers; update Fleet README and portfolio status. All claims must be current and scoped. See [OpenAI Codex `AGENTS.md` guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md): concise durable rules, deeper documentation referenced as needed. `SESSION_NOTES.md` is an explicit project workflow file, **not** an automatically loaded Codex instruction source; `AGENTS.md` must point to it.

### A-05 — Site chat service transport coupling — P2, confirmed

**Evidence:** `backend/app/services/chat.py` 640 lines, `stream_answer` and `_stream_rag_answer` implement backpressure-safe token emission, fallbacks, unsafe-output blocking and `ServerSentEvent` creation. `backend/app/api/sse.py` handles serialization and header framing.

**Action:** keep orchestration and safety decisions, extract only event mapping or return typed application stream events mapped at API boundary. Pin golden JSON/SSE test fixtures including `retrieval_status`, `case_id`, `case_section`, `meta`, `token`, `sources`, `done`, error and safety fallback. Do not accidentally remove buffer semantics, call ordering or async yielding.

### A-06 — Frontend chat hook concentration — P2, confirmed

**Evidence:** `frontend/hooks/use-chat-controller.ts` 632 lines, multiple correlated `useState`, callbacks and async paths; it already composes `useEscalationStream` and external API helpers. `ChatShell` is primarily a presentation component, but still 447 lines.

**Action:** identify races and write E2E/component characterization tests for stream abort/reset, duplicate handoff events, fallback, reconnect, close, keyboard focus and fast user interactions. Extract *pure transitions* first, then isolate warmup and AI/handoff flows if seams are stable. Do not simultaneously redesign UI or change source reveal animations.

### A-07 — Qdrant adapter and RAG routing modules are large — P2/P3, confirmed size, refactor conditional

**Evidence:** `backend/app/rag/qdrant_store.py` 617 lines handles collection creation, payload indexes, ingest/upsert/delete/version cleanup, searches and contract checks. `qdrant_retriever.py` ~500 lines selects cases, embeds queries, searches and reranks. `query_router.py` ~602 lines includes long `ROUTING_RULES` tables and routing logic.

**Action:** **do not** move RAG to separate service. First profile functions/tests and identify true independent change axes. Candidate separation: query-routing rule data from matching engine; Qdrant read adapter from ingestion/admin lifecycle. Preserve shared `RagCollectionContract`, versioned ingestion guarantees, collection probe, source filters and public answer evaluations. This is lower priority than Fleet DB and boundary checks.

### A-08 — Fleet frontend queue component — P3, candidate

`portfolio/fleet_hub/frontend/src/operations/OperationsQueuePanel.tsx` 450 lines with status formatting and queue presentation. Size alone does not prove a god module. Separate API fetching, data transformations and view only **if** characterization demonstrates independent responsibilities or frequent conflicting changes. Other inspected Fleet components are shorter (`OperationsPanel.tsx` ~98, `FleetApp.tsx` ~128).

### A-09 — Escalation schema DTOs and handoff constants — P3, confirmed but *not* urgent

`EscalationService` directly accepts request schemas and emits SSE models; small-site layered FastAPI systems may intentionally use Pydantic DTOs internally. Introduce internal DTOs only when a second transport or complex domain makes the boundary valuable. Handoff constants in `ChatService` can move with A-05, not as a cosmetic standalone migration.

## Target skeleton (evolutionary, not a big-bang migration)

```text
backend/app/
  api/                   HTTP/validation, SSE serialization
  services/              site use-case orchestration; no FastAPI Request/Response
  domain/                NEW only for genuinely shared pure state (escalation_session.py)
  repositories/          site persistence adapters (depend on domain, not services)
  rag/, llm/             retain existing RAG/provider design
  core/                  config, logging, metrics; not a dumping ground
portfolio/fleet_hub/backend/src/fleet_hub/
  router.py              single public API entry
  api/                   route handlers, dependencies.py, optional schemas
  services/              existing use cases, narrowed by task
  domain/                ADD only when pure Fleet rules are extracted
  persistence/           ADD shared SQLite connection, versioned migrations, DB operations
  integrations/          ADD only if external email adapter needs isolation
portfolio/fleet_hub/frontend/src/
  index.ts               single public host import
  <feature>/             feature-local component, state, styles, API adapter as needed
frontend/app/fleet-vor-hub/   route adapters only
```

**Allowed arrows:** website FastAPI host → `fleet_hub.router`; Fleet HTTP router → Fleet use cases → Fleet persistence and pure rules; infrastructure → pure domain types; website frontend adapter → `@fleet-hub`; Fleet frontend → only its own code + allowed framework packages. Never introduce `domain → api/services/infrastructure`, `repository → services`, `fleet_hub → host website business code`, or sibling-router imports for shared auth. Avoid forcing full hexagonal architecture on this small demo: use the smallest seams that make dependencies testable.

## Reviewable commits / PR sequence

Use **one coherent concern per PR** rather than a single giant refactor. Do not create a docs-only PR: bootstrap audit + ledger are included in the first real Fleet DB refactoring PR, on `refactor/architecture-boundaries-2026-11-02`. Every PR updates `SESSION_NOTES.md`, runs `task ci`, records actual evidence and avoids feature changes.

| PR | Suggested branch | Commit subject | Work / exit criterion |
|---|---|---|---|
| 1 | `refactor/architecture-boundaries-2026-11-02` | `♻️ refactor(fleet-db): separate initialization from request paths` | **First code PR:** commit audit + ledger TOGETHER with Fleet DB characterization tests (steps 00 + 01) and real connection/migration refactor (step 02). Tests cover fresh/legacy temp SQLite, repeat open, concurrency, rollback and data safety. Preserve schema, seed, API and runtime path, run `task ci`. Do not open a docs-only PR. |
| 2 | `refactor/fleet-api-delivery-boundaries` | `♻️ refactor(fleet): isolate auth dependencies and mail orchestration` | Extract router-shared auth/origin dependencies and send-email use case; dependency fakes and failure tests; preserve HTTP, cookie and recipient policy. |
| 3 | `refactor/dependency-direction` | `♻️ refactor(architecture): enforce layered imports` | Move escalation state to neutral domain, update repository imports; add AST/TS boundary checks; no transport/API changes. |
| 4 | `refactor/chat-stream-boundary` | `♻️ refactor(chat): decouple stream event mapping` | Isolate SSE mapping while preserving streaming safety and public payloads; golden JSON/SSE tests. |
| 5 | `refactor/chat-controller-seams` | `♻️ refactor(frontend-chat): extract controller transitions` | Characterization tests first, then narrow controller state/action seams; preserve UX. |
| 6 | (included in appropriate refactor PR) | (no separate docs-only commit) | Update `AGENTS.md`, README and portfolio status as part of the code PR that changes those contracts; archive old historical notes where necessary. |

**Optional later work:** A-07 RAG adapter/rules split, A-08 Fleet queue component split, A-09 DTO/copy cleanup — require justification by actual coupling or change frequency. There is no dedicated PR for line-count cosmetics.

### Mandatory validation gates

1. Run `task ci` locally and in PR CI; record real outcomes, not unchecked `- [x]` placeholders. For focused checks use `task backend:test`, `task backend:lint`, `task backend:format-check`, `task portfolio:check`; frontend `npm run lint`, `npm run typecheck`, `npm run e2e` where applicable.
2. Fleet: preserve route method list (reported 56), login/logout cookie and CSRF/Origin, email failure/allowlist/quota, full data workflow, SQLite runtime path and seed SHA. Never run destructive tests against an existing `_local` or production DB.
3. Site: verify chat JSON and SSE `meta/token/sources/done/error`, retrieval confidence/status, safety fallbacks, escalation stream and Telegram, RAG canary/contract eval.
4. Frontend: E2E desktop/mobile for login/handoff/stream/reset and Fleet navigation. Preserve Vercel/Render shared host and noindex Fleet visibility.
5. Before merge: diff inspection, new import guard tests, no public contract drift, `SESSION_NOTES.md` row updated with exact commit/PR or blocker. GitHub merge/deploy require explicit operator action.

## Confidence

- **High:** current source confirms the import inversion, Fleet/router responsibilities, DB lifecycle call sites, long modules and outdated repo notes.
- **Medium:** exact optimal refactor decomposition and potential concurrency/performance implications; test first.
- **Not established:** full repository-wide dependency graph, bugs at runtime, current CI status on the audit machine, external deployment health, original 14-issue report.

## Implementation checkpoint (2026-11-04; unmerged branch)

This is a **historical audit of `main@88b24f5`**, not a live description of
all open findings. In branch `refactor/architecture-boundaries-2026-11-02`,
GitHub HEAD `4da72d53b314` includes the Fleet SQLite extraction, v1/v2/ops
readiness probes, interprocess bootstrap locking, startup hook, lock-free warm
connection path, and v1 per-version failure rollback tests. The user reported
green tests for the final code patch. The documentation synchronization and
first architecture PR remain pending; independent PR CI is not claimed.

Outstanding follow-up concerns remain Fleet HTTP/email boundaries, backend
repository dependency inversion and Chat/SSE/controller structure. Do not
conflate these later PRs with the Fleet SQLite release gate.
