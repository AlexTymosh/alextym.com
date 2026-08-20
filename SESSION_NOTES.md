# RAG and chat reliability work

Last updated: 2026-08-19

Branch: `codex/fix-rag-chat-reliability`

## Work boundary

This branch is for the confirmed production RAG failure and the related chat
reliability defects discovered during the investigation. Keep changes scoped to:

- the Qdrant collection contract, readiness, failure semantics, and observability;
- query routing, case selection, section retrieval, and retrieval evaluation;
- structured contextualization of ambiguous follow-up messages;
- frontend handoff suggestion and dismissal behavior;
- tests and documentation required to verify those changes.

Do not change production environment variables, ingest or delete Qdrant data,
push the branch, or open a pull request without explicit approval.

## Confirmed findings

1. Production is configured for `alex_public_knowledge_named` in `named` vector
   mode. That stale collection does not have the indexed `source_group` field now
   required by every runtime retrieval. Qdrant rejects the query with HTTP 400:
   `Index required but not found for "source_group"`.
2. The chat service catches that provider/schema failure and returns the same
   response used for genuinely empty knowledge. The UI therefore reports
   insufficient public information instead of a technical retrieval failure.
3. `/api/health/ready` checks only whether provider settings are present. It does
   not validate the configured collection, vector schema, payload indexes, or a
   read-only search contract.
4. The current query router uses broad substring matches. In particular,
   `limitations` is misrouted to personal development areas and `service` is
   misrouted to commercial services. With neutral routing, both affected case
   studies rank first.
5. Live retrieval evaluation currently passes 15 of 20 cases. The remaining
   failures also show that candidate retrieval and final result count are
   conflated and that section intent is not modelled explicitly.
6. The follow-up contextualizer asks the generic LLM client for free-form JSON.
   The model correctly resolves `yes`, but a numeric confidence value fails the
   schema that requires `low`, `medium`, or `high`; the valid meaning is then
   discarded and replaced with a clarification response.
7. The frontend handoff detector matches `Give me Alex's 30-second intro` as a
   human handoff request. The frontend also derives handoff state from arbitrary
   message text instead of relying on structured backend/message metadata.
8. `Continue with AI` does not send a request. It only dismisses the handoff card
   and focuses the input, so its label promises behavior the control does not
   perform.

## Telegram local development verification

The repository intentionally supports a separate local Telegram bot:

- the backend reads `TELEGRAM_BOT_TOKEN`;
- the local polling bridge reads `TELEGRAM_DEV_BOT_TOKEN`;
- `telegram-dev-preflight.ps1` requires both local values to identify the same
  dev bot and verifies `TELEGRAM_DEV_BOT_USERNAME` through Telegram `getMe`;
- the deployed backend receives its separate `TELEGRAM_BOT_TOKEN` from Render.

`TELEGRAM_BOT_TOKEN_REAL` is not referenced by application code, scripts,
Taskfile tasks, examples, or documentation. In the ignored local `backend/.env`:

- it has an accidental double `=` delimiter;
- after normalizing that delimiter, it equals the configured local dev token;
- it is therefore a redundant local alias, not part of the two-bot design;
- its malformed syntax causes `uv --env-file` to print an unsafe parser warning.

Do not commit or print any token value. The recommended local cleanup is to
remove the unused `TELEGRAM_BOT_TOKEN_REAL` line and keep only the documented
`TELEGRAM_BOT_TOKEN` plus `TELEGRAM_DEV_BOT_TOKEN` contract. This cleanup has not
been performed.

## Target architecture

1. Define one shared `RagCollectionContract` used by ingestion, runtime search,
   readiness checks, deployment validation, and tests.
2. Standardize production retrieval on the evaluated single `body_dense` vector.
   Keep named vectors out of production until fusion is implemented and proves a
   measurable evaluation benefit.
3. Use a stable Qdrant alias over versioned physical collections so ingestion can
   build, validate, smoke-test, and atomically activate a compatible dataset.
4. Separate routing dimensions: source scope, subject/domain hints, requested
   section, and handoff policy. Broad hints must not become exclusionary filters.
5. Use two-stage case-study retrieval: select a case from a wider candidate pool,
   then retrieve and rank sections inside that case before returning the final
   bounded result set.
6. Introduce typed retrieval outcomes. Distinguish empty knowledge from embedding,
   provider, collection-contract, and vector-search failures without exposing raw
   provider errors to users.
7. Use an OpenAI structured-output adapter for contextualization instead of
   parsing free-form text returned by the general answer client.
8. Make structured message/backend flags authoritative for handoff UI. Treat card
   dismissal as a UI action tied to a message ID and label it according to its
   actual behavior.

## Delivery plan: one PR, five technical steps

The work is planned as one pull request with five sequential technical commits.
After every step:

- update the status table and verification log in this file;
- run the checks scoped to that step;
- stop and report the result;
- provide a Conventional Commits message;
- continue only after the user confirms the local commit.

| Step | Commit scope | Required result |
| --- | --- | --- |
| 1 | `fix(rag): enforce the production collection contract` | Qdrant contract validation, truthful readiness, typed retrieval failures, safe metrics/logs, and focused backend tests |
| 2 | `refactor(rag): separate case selection from section retrieval` | Boundary-aware routing, wider candidate retrieval, case-to-section ranking, and passing live retrieval evaluation |
| 3 | `fix(chat): use structured follow-up contextualization` | Provider-enforced structured output and passing ambiguous follow-up scenarios including `yes` |
| 4 | `fix(chat-ui): make handoff suggestions explicit` | Structured handoff state, no quick-prompt false positive, accurate dismissal semantics, and Playwright coverage |
| 5 | `chore(release): add RAG deployment verification` | Read-only contract probe, production canaries, complete JSON/SSE and eval verification, and updated documentation |

The current `SESSION_NOTES.md` setup is preparatory work and is not one of the
five technical steps. If committed separately, the branch will contain six local
commits before any optional squash.

## Execution plan

### Phase 1 - Collection contract and failure semantics

- Add the shared collection contract and validation service.
- Validate vector mode, vector name/dimension, required payload indexes, point
  availability, and expected public source groups.
- Keep liveness cheap; expose cached dependency state through readiness.
- Map technical retrieval failures to a typed temporary-unavailable response.
- Add bounded metrics and safe logs by retrieval stage/error code.
- Add unit and integration tests for missing indexes, wrong vector mode, empty
  search, and provider failure.

### Phase 2 - Retrieval architecture and quality

- Replace substring routing with boundary-aware, precedence-tested routing.
- Separate commercial-service intent from case-study service-design questions.
- Model requested case sections such as problem, analysis, implementation,
  validation, limitations, and results.
- Retrieve a wider candidate pool, group/rank case candidates, then retrieve the
  selected case sections and truncate only after reranking.
- Run the complete live retrieval suite and investigate every remaining failure.

### Phase 3 - Structured follow-up contextualization

- Add a dedicated provider interface for structured question resolution.
- Use provider-enforced structured output matching `ContextualizedQuestion`.
- Preserve frontend-generated assistant messages in bounded history.
- Cover `yes`, pronouns, ambiguous continuations, low confidence, invalid output,
  and provider failure.

### Phase 4 - Frontend handoff state

- Remove broad frontend inference from arbitrary user and assistant text.
- Preserve explicit structured handoff flags on scripted and backend messages.
- Rename `Continue with AI` to an accurate dismissal label such as `Not now`.
- Track dismissal by the triggering message ID.
- Add Playwright coverage for the 30-second intro, genuine handoff requests,
  dismissal, `yes` follow-up, JSON fallback, and SSE completion.

### Phase 5 - Release controls

- Add a read-only collection-contract deployment probe.
- Add production canary questions that require non-empty sources and known case
  IDs/sections.
- Require JSON/SSE parity, backend checks, frontend checks, retrieval evals, and
  answer evals before deployment.
- Deploy only after the target collection passes the contract and canary; verify
  that Qdrant 400 retrieval errors remain at zero after activation.
- Update RAG, API, deployment, architecture, and security documentation.

## Status table

Status values: `COMPLETE`, `IN_PROGRESS`, `PENDING`, `BLOCKED`.

Current stage: Phase 4 is complete and awaiting the user's local commit. Phase 5
has not started.

| ID | Work item | Status | Evidence / current result | Next gate |
| --- | --- | --- | --- | --- |
| 0.1 | Create local work branch | COMPLETE | `codex/fix-rag-chat-reliability` created from clean `main` | Keep work local until push approval |
| 0.2 | Confirm production RAG root cause | COMPLETE | Named collection rejects required `source_group` filter with Qdrant HTTP 400 | Preserve as regression test |
| 0.3 | Verify current public collection | COMPLETE | Single-vector collection has 115 points and returns relevant sources | Formalize contract |
| 0.4 | Run baseline retrieval evaluation | COMPLETE | 15/20 cases pass | Reach full expected-case/section coverage |
| 0.5 | Verify Telegram two-bot setup | COMPLETE | Local backend/dev tokens match; production uses separate Render environment; unused `TELEGRAM_BOT_TOKEN_REAL` confirmed | Local cleanup requires approval |
| 1.1 | Implement shared collection contract | COMPLETE | Shared contract validates canonical vector schema, required keyword indexes, points, and public source groups | Preserve contract in later retrieval changes |
| 1.2 | Add cached readiness contract check | COMPLETE | Read-only Qdrant probe returns `not_ready` and HTTP 503 on contract failure; liveness remains provider-free | Add the production deployment gate in Phase 5 |
| 1.3 | Add typed retrieval failure semantics and observability | COMPLETE | JSON/SSE expose `empty` vs `unavailable`; bounded stage/error metrics and safe logs added | Preserve status parity in later chat changes |
| 2.1 | Redesign query routing dimensions | COMPLETE | Boundary-aware phrase routing separates subject hints, source scope, and case-section intent; targeted regressions pass | Preserve dimensions through retrieval eval |
| 2.2 | Implement two-stage case/section retrieval | COMPLETE | Subject-only case selection groups at least 36 candidates; selected-case retrieval reranks at least 18 sections before final limit | Preserve stage separation in later changes |
| 2.3 | Pass live retrieval evaluation | COMPLETE | Final live suite passes 20/20, up from 15/20, with zero regressions | Re-run as a release gate in Phase 5 |
| 3.1 | Implement structured contextualizer adapter | COMPLETE | Dedicated dependency uses OpenAI `responses.parse` with the closed `ContextualizedQuestion` schema; answer generation remains separate | Preserve provider contract and metrics |
| 3.2 | Verify ambiguous follow-up scenarios | COMPLETE | `yes`, pronouns, low confidence, invalid output, and provider failure pass; live `yes` returns retrieval success with six experience sources | Commit Phase 3 before starting Phase 4 |
| 4.1 | Make handoff metadata authoritative | COMPLETE | Typed and scripted assistant messages carry explicit metadata; typed handoff requests always route through backend JSON/SSE metadata; text and `not_enough_data` inference removed | Preserve the contract in release controls |
| 4.2 | Correct dismissal semantics and label | COMPLETE | `Not now` dismisses only the triggering assistant message ID; a later independent suggestion remains eligible | Preserve message identity across UI changes |
| 4.3 | Add end-to-end chat/handoff coverage | COMPLETE | Desktop/mobile tests cover the 30-second intro, metadata true/false, direct request routing, message-scoped dismissal, frontend history, JSON fallback, SSE, and active handoff | Commit Phase 4 before starting Phase 5 |
| 5.1 | Run complete local verification | PENDING | Phase 4 `task ci` passes; Phase 5 release probes and canaries are not implemented | Start only after the Phase 4 commit is confirmed |
| 5.2 | Validate target Qdrant collection and canaries | PENDING | Production change not authorized | Explicit deployment approval |
| 5.3 | Prepare commit and PR text | PENDING | Commits remain user-managed | Complete verification |

## Verification log

| Date | Check | Result |
| --- | --- | --- |
| 2026-08-19 | Git worktree before branch creation | Clean; `main` matched `origin/main` |
| 2026-08-19 | Production `/api/chat` and Qdrant telemetry | Insufficient-data response coincides with Qdrant query HTTP 400 |
| 2026-08-19 | Exact named-collection query | Reproduced missing indexed `source_group` error |
| 2026-08-19 | Current single-collection retrieval | Relevant chunks returned above configured threshold |
| 2026-08-19 | Live retrieval evaluation | 15 passed, 5 failed |
| 2026-08-19 | Neutral-route diagnostic | Credit-risk and international-employment cases both rank first |
| 2026-08-19 | Telegram environment contract | Local backend and poller use the same dev bot; unused REAL alias is malformed and redundant |
| 2026-08-19 | Phase 1 focused backend tests | 47 passed; collection contract, readiness cache, provider failures, JSON/SSE parity, metrics, and safe logs covered |
| 2026-08-19 | `task backend:check` | Ruff, format, compile, and all 399 backend tests passed; one existing Starlette deprecation warning |
| 2026-08-19 | `task frontend:check` | ESLint, TypeScript, resume parser, production build, and all 62 Playwright tests passed |
| 2026-08-19 | `task ci` | All eight local gates passed, including 27/27 chat eval, free RAG checks, and Docker build |
| 2026-08-19 | Phase 2 targeted retrieval tests | 32 passed initially; broader retrieval suite passed after using workspace-local pytest temp storage |
| 2026-08-19 | Phase 2 live retrieval evaluation | Improved 15/20 to 18/20, then 20/20 after separating subject-level case selection from section intent; zero regressions |
| 2026-08-19 | Phase 2 `task backend:check` | Ruff, format, compile, and all 407 backend tests passed; one existing Starlette deprecation warning |
| 2026-08-19 | Phase 2 `task ci` | All eight local gates passed: repository/config checks, backend, frontend, free RAG, and Docker build |
| 2026-08-19 | Phase 3 pre-fix regression | Numeric `confidence: 0.95` discarded a valid `yes` resolution: 1 failed, 7 passed |
| 2026-08-19 | Phase 3 targeted contextualization tests | 46 passed across provider schema, routing, JSON/SSE integration, RAG flow, and metrics |
| 2026-08-19 | Phase 3 live structured contextualization | Exact frontend-scripted offer plus `yes` returned `alex_profile_question`, a standalone experience question, and `confidence: high` |
| 2026-08-19 | Phase 3 live end-to-end follow-up | Contextualization, embedding, Qdrant retrieval, and answer generation completed with `retrieval_status: success`, six experience sources, and no clarification |
| 2026-08-19 | Phase 3 `task backend:check` | Ruff, format, compile, and all 411 backend tests passed; one existing Starlette deprecation warning |
| 2026-08-19 | Phase 3 `task ci` | All eight local gates passed: backend 411/411, frontend Playwright 62/62, chat eval 27/27, free RAG, and Docker build |
| 2026-08-19 | Phase 4 targeted frontend checks | Project config, ESLint, TypeScript, and 28 desktop/mobile handoff/history scenarios passed |
| 2026-08-19 | Phase 4 `task frontend:check` | ESLint, TypeScript, resume parser, production build, and all 70 Playwright tests passed; npm audit reports one existing high-severity dependency finding |
| 2026-08-19 | Phase 4 `task ci` | All eight local gates passed: backend 411/411, frontend 70/70, chat eval 27/27, free RAG, and Docker build |

Update the status table and verification log as each phase progresses. Do not mark
an item complete until its implementation and stated verification gate both pass.
