# Main website — Stage 17 release audit

**Audit date (UTC):** 2026-11-09  
**Baseline:** `main` at `65bb47ced7965987d8a8d90c7294b612ab3b3f35` (PR #241).  
**Status:** **IN PROGRESS — NOT RELEASE-SIGNED-OFF**.  
**Scope:** main Next.js website, FastAPI site APIs, RAG/LLM, Chat/Handoff, deployment and security. Fleet VOR Hub internals are excluded; its compatibility checks stay in CI.

This is an evidence-based audit, not a claim that every external service or vulnerability feed is healthy. Historical files (including the 2026-11-02 architecture audit) describe older snapshots and must not be treated as the current implementation state.

## 1. Verified evidence

| Gate | Evidence captured | Result / limits |
|---|---|---|
| Stage 16 merged | GitHub PR #241, merged 2026-11-09 19:53 UTC | **PASS**: changes in `main` SHA `65bb47ce`. |
| GitHub primary CI | [run 42687716464](https://github.com/AlexTymosh/alextym.com/actions/runs/42687716464): project, backend, frontend, rag, docker | **5/5 PASS** on SHA `65bb47ce`. These are repository CI checks, not live infrastructure probes. |
| CodeQL workflow | [run 42687715367](https://github.com/AlexTymosh/alextym.com/actions/runs/42687715367): actions, JavaScript/TypeScript, Python analyses | **3/3 PASS**. This does **not** prove that there are zero open security alerts. |
| Vercel production build | [deployment Dr1pbcFXis7Y84xoBBw3SCufEais](https://vercel.com/alextym/alextym-com/Dr1pbcFXis7Y84xoBBw3SCufEais) | **READY**, target `production`, Git SHA exactly `65bb47ce`. Not an HTTP/functional test. |
| Frontend domains | Vercel project `alextym-com`, domains `alextym.com`, `www.alextym.com` | Both verified in Vercel; `www` configured with 308 redirect to apex. Live redirect HTTP not independently measured. |
| Backend container topology | `backend/Dockerfile` at baseline | The Docker build copies the local Fleet backend project and its `src` before frozen `uv sync`; GitHub `docker` job passed. |
| Public API rewrite | `frontend/next.config.mjs` at baseline | `BACKEND_ORIGIN` is required for Vercel builds and used to rewrite `/api/:path*` to backend. Does not prove that the configured origin is online. |
| Architecture guard | `backend/scripts/check_import_boundaries.py` and site/Fleet tests | Included in successful backend CI; AST-based static guard with documented computed-import limitations. |
| Security/privacy implementation | `backend/app/core/logging.py`, `backend/app/api/rate_limit.py`, `backend/app/main.py`, `docs/security-privacy.md` | Keys/redaction, ASGI peer selection, and CORS configuration are implemented; their **production effectiveness remains unverified**. |

## 2. Pending external gates (release blockers)

| ID | Risk / verification | Severity for release | Evidence needed | Owner / state |
|---|---|---|---|---|
| R17-01 | Render backend deployment is running the intended SHA and is reachable | HIGH: release gate | Authorized Render workspace, service ID, live deploy SHA and direct `/api/health/live` + `/api/health/ready` responses | PENDING. Connector requires the user to confirm the workspace; no selection was made. |
| R17-02 | Production frontend rewrite to backend works end-to-end | HIGH: release gate | Read-only HTTP GET on apex `/`, `/chat`, `/api/health/live`, `/api/health/ready` and response/schema evidence | PENDING. Direct public HTTP access failed from audit tooling; do not infer downtime. |
| R17-03 | Live Upstash REST/EVAL/TTL/DEL semantics | HIGH: release gate | Four opt-in tests against **isolated non-production** Upstash credentials; store only redacted pass/fail | PENDING from Stage 11. Unit simulations and CI skips do not substitute for this. |
| R17-04 | Trusted ASGI peer identifies distinct clients correctly behind production proxy | HIGH: privacy/cost/availability risk until validated | Controlled two-client request test, trusted proxy configuration and rate-limit evidence, without exceeding quotas | PENDING from Stage 12. Spoof regression tests in CI do not prove production proxy topology. |
| R17-05 | Live RAG readiness, retrieval quality, JSON/SSE parity and baseline comparison | HIGH: release gate | `rag:release:predeploy`, `rag:release:postdeploy`, controlled before/after report, explicit model/config/version evidence | PENDING: credentials, execution and frozen baseline not available in this audit environment. Live tests may incur provider cost. |
| R17-06 | Browser Chat/Handoff and contact/Telegram availability under real production conditions | HIGH: release gate | Non-sensitive scripted Chat checks, manual consent-based handoff/contact/Telegram tests and reset/timeout observation | PENDING. No outbound customer message or Telegram side-effect was triggered during this audit. |
| R17-07 | Open vulnerability advisories / dependencies | MEDIUM until triaged; escalates if critical/high | `npm audit`, backend lockfile advisory scan, GitHub Dependabot/CodeQL alert review, remediation decision | PENDING. Six open Dependabot **update PRs** were observed; update PR count is not a vulnerability count. Private security alert endpoints were not accessible to audit tooling. |
| R17-08 | Production headers, CORS and observability/PII redaction | MEDIUM | HTTP response header evidence; security-origin test; limited redacted log sample and Grafana error counters | PENDING. Code-review assertions only. |

**Release decision:** **NO SIGN-OFF** until R17-01 through R17-06 have recorded evidence and all critical/high alerts are fixed or explicitly accepted with rationale and owner. R17-07 and R17-08 must also be triaged and documented before final sign-off.

## 3. Architectural inventory and ownership

```text
frontend/app                   Next.js routes and deployment host
frontend/components, hooks     UI and Chat controller (Stage 16 handoff lease)
frontend/lib                   Chat transport, request lifecycle, response flow
backend/app/api                FastAPI HTTP and SSE adapters
backend/app/services           Site application orchestration
backend/app/domain             Pure Chat/Handoff domain state and event models
backend/app/repositories       Site storage implementations (Upstash etc.)
backend/app/rag, app/llm       Retrieval, prompt and provider integration
backend/app/core, middleware  Configuration, telemetry, request identity
portfolio/fleet_hub            Separately owned installable demo feature
```

Verified static composition: one Next.js host, one FastAPI host mounting the optional Fleet router, backend Docker includes the local Fleet package. The AST guard rejects documented forbidden direction imports. No evidence supports replacing this with microservices or splitting the React controller solely due to file length.

## 4. Security and operational review observations

- **Client identity:** rate limit derives from the ASGI peer and deliberately ignores untrusted forwarding headers. This prevents simple header spoofing in code, but proxy configuration may make many visitors share one observed peer; verify with two clients in production before accepting.
- **Redis failover:** the in-memory fallback is process-local, restarts reset counters, and multiple replicas do not share limits. Document this as an accepted limitation only if production topology and quotas make it safe.
- **PII/logging:** `SENSITIVE_LOG_KEYS` redacts named sensitive top-level fields. Audit nested exception contexts and integration-level logs separately; the current static review does not prove total PII absence.
- **CORS:** the backend restricts origins to the configured frontend (with extra localhost origins for development), `allow_credentials=False`. Review production headers/CSRF and direct-backend exposure using controlled requests.
- **Transport:** Chat and Escalation both use SSE adapters with explicit stream closing. CI passed but no real disconnected-client or retry latency was measured in production.
- **Deployment:** `READY` in Vercel covers the frontend deployment state. Render health, Qdrant, OpenAI, Upstash and Telegram must be verified independently.
- **Dependencies:** CodeQL job success is not a full dependency-advisory audit. GitHub dependency update PRs require separate compatibility/security review; avoid merging major version upgrades into release verification without targeted testing.

## 5. Evidence checklist for sign-off

- [x] Main commit, PR merge, five CI jobs and three CodeQL analysis jobs recorded.
- [x] Matching Vercel production commit and configured apex/`www` domains recorded.
- [x] Static architecture, Docker, rewrite, core security and RAG test interfaces reviewed.
- [ ] Read-only HTTP status/schema probe against live apex and **separate** backend origin.
- [ ] Confirmed Render service deployment, SHA and health/readiness.
- [ ] Isolated non-production Upstash REST/EVAL contract tests PASS.
- [ ] Verified production proxy peer identity and rate-limit isolation.
- [ ] Non-destructive RAG canaries; before/after quality comparison against frozen baseline.
- [ ] Browser Chat/Handoff, contact consent and Telegram manual integration checks.
- [ ] Security header/CORS review; dependency advisory and audit triage.
- [ ] Confirm final release SHA and close or accept all HIGH/CRITICAL findings.

## 6. Next actions

Use `docs/runbooks/site-release-verification.md`, `scripts/site_release_probe.py` and the optional, untracked Stage 17 verifier (distributed in the original Stage 17 package). Keep their generated results under ignored `.tmp/release-evidence/`; never commit tokens, transcripts, visitor messages or raw provider responses. Final approval must record date, reviewer role, commit SHA, Render/Vercel deployment IDs, test results and risk acceptance. Do not mark Stage 17 DONE based on unit tests alone.


## 7. Stage 17 repository/tooling cleanup

One-time Fleet migration-preservation checks and per-person demo configuration
were retired. The original Portfolio foundation checker was replaced with a
publication-neutral registry contract check; runtime route/isolation checks
remain in `task portfolio:check`. The temporary Stage 17 verifier is kept out
of Git: use the downloaded script, or run the three commands in the runbook.
The long execution ledger was archived in `docs/archive/` and the active
`SESSION_NOTES.md` was shortened. These are maintenance changes only: they do
not close any pending production, security or integration release gate.
