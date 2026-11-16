# Workforce & Recruitment Intelligence — Implementation Session Notes

**Project:** `workforce_intelligence`  
**Document status:** PRs 1–7 merged. The current follow-up gives Workforce a full-page layout and updates the synthetic employee directory.

**Plan version:** 1.0  
**Prepared:** 2026-11-14  
**Primary specification:** `docs/specifications/SCAS_Workforce_Recruitment_Intelligence_POC_Technical_Specification_v1.2.md`  
**Project session-notes path:** `portfolio/workforce_intelligence/SESSION_NOTES.md`  
**Initial implementation branch:** `feat/workforce-intelligence-foundation`  
**Target:** 7 sequential PRs, **21 intentional working commits** (3 per PR); squash-merge each PR to `main` where preferred  
**Milestone:** Interview MVP after PR 3; complete PoC after PR 7

> This is a living handoff and execution tracker, not evidence that a feature has been implemented. Keep the status, commit SHA, PR number, test evidence and any deviations updated **after every commit**. Future coding sessions should read this file and the relevant sections of the specification before making changes.

---

## 0. Decision summary and source of truth

**Owner decision for the 16 November interview:** defer Firebase integration
for this project. Use the current shared demo password with a distinct
Workforce-signed session and no individual identity. This supersedes the earlier
Workforce Firebase admission choices below for the interview deployment;
Portfolio Lab's separate identity work is unchanged.

The authoritative product scope is the English specification v1.2 named above. This plan groups its requirements for implementation; it does **not** redefine, delete or silently waive the full-PoC requirements. The original full specification includes four functional modes, synthetic workforce/recruitment data, temporal history, governed metrics, People Voice, evidence-linked AI, Excel ingestion, forecasting, architecture views and guided interview scenarios.

Confirmed implementation constraints:

1. **One monorepo and one shared deployment footprint.** Next.js/React on Vercel, FastAPI on Render. The project lives in `portfolio/workforce_intelligence/`, next to the existing `portfolio/fleet_hub/`. Preserve Fleet and the public website.
2. **Canonical URLs:** host-owned catalogue `/portfolio`; protected app `/portfolio/workforce-intelligence`; project API `/api/workforce/*`. The Workforce UI uses SPA-like client-side navigation within the existing Next.js app, not a separately deployed SPA.
3. **Visual direction:** Fleet-inspired density, layout and palette; no Fleet-internal component imports or global CSS coupling. Keep project-local styles; factor a neutral shared primitive only after demonstrable reuse.
4. **Login:** reuse Firebase Authentication email/password, existing Next.js session and FastAPI credential verification. Owner provisions and privately sends credentials. Google, GitHub and Microsoft are deferred and do not block this project.
5. **One effective app role:** `Member` for every explicitly granted participant. No project-owned passwords, account records, hierarchical roles or alternate session mechanism.
6. **Authorization remains a dependency.** Firebase identity admission is **not** a project grant. Shared Portfolio Lab project-grant verification must be implemented/reused before non-Owner access; protect both the Next.js entry/BFF and direct Render origin. A restricted Owner-only preview is a temporary integration option, not a public release.
7. **One access level, including reset:** the platform's existing `Test` capability alone does not authorize reset, while v1.2 requires all Members to be able to reset. Use **one fixed project-scoped `Admin`-capable grant for Workforce Members** (or an equivalent minimal shared capability bundle approved in the platform's RBAC design). The Workforce UI/domain calls this `Member`, never `Admin`. Global `Owner` authority, identity management and project-grant administration remain separate. Record the final mapping in the ADR and spec (§5.2) before enabling testers.
8. **Persistence:** dedicated Workforce SQLite with project-owned schema, migrations, deterministic seed and local audit; Render may reset it. Firestore is only shared durable identity/grants/security control-plane storage; do not store Workforce operational/Gold data there. Separate from Fleet SQLite.
9. **No new paid infrastructure**, additional React app, database server, microservice, new top-level state-management framework, or speculative generic portfolio plugin architecture.
10. **Synthetic-only data:** never load real SCAS people or sensitive HR records. Source public benchmarks separately and cite them. Permanent unofficial/synthetic notice.

### Specification path reconciliation

The v1.2 file was saved in `docs/specifications/`, whereas its own header/Appendix B suggests `portfolio/workforce_intelligence/docs/technical-specification.md`. **Use the user's actual tracked path above as the single canonical copy** for this implementation. In PR 1, correct the spec's `Document location in repository` metadata and blueprint or add a short link there; do **not** maintain two diverging full specification files. Project `README.md` links to that canonical spec.

### Existing platform references (verify again at PR start)

- `docs/specifications/portfolio-lab-auth-access.md` — global identity, grants and security policy.
- `docs/adr/0001-portfolio-lab-identity-access.md` — approved shared trust boundaries.
- `docs/architecture/portfolio.md` — host/project ownership; may contain stale implementation-status text.
- `portfolio/catalog/registry.json` — registered project IDs; at planning baseline `fleet_hub` only.
- `portfolio/fleet_hub/project.json` and `portfolio/fleet_hub/README.md` — manifest conventions, packaging, lifecycle and protected compatibility boundaries.
- `frontend/app/lab/*`, `frontend/lib/portfolio-lab/*`, `backend/app/security/*` — current Firebase identity infrastructure; **not yet a completed grant-based RBAC service** at the 2026-11-14 checkpoint.
- `frontend/next.config.mjs` — `/api/*` rewrite. An `HttpOnly` website cookie does not automatically reach Render.
- `backend/app/main.py` — shared router/optional demo startup composition.
- `Taskfile.yml`, `.github/workflows/ci.yml`, `scripts/check-registered-project-boundaries.mjs`, `scripts/check-website-portfolio-boundaries.mjs`, `backend/scripts/check_import_boundaries.py` — repository verification and ownership checks.

**Git checkpoint examined when planning:** Firebase identity PR #244 was merged into `main` at `5d9a120a0b5ac795a47ffdc84661704725f89660`. This is only a planning baseline; check the latest `main` immediately before coding.

---

## 1. Delivery model and why 21 commits

**Seven coherent review units × three meaningful commits = 21 planned working commits.** One commit should produce one testable architectural capability or feature slice, not an arbitrary file count. The working-commit count is a target, not a limit: split an unsafe oversized change if tests/review demand it; do not create ceremonial commits to reach 21.

- **PR 1–3 (9 commits):** a protected, testable **Interview MVP** with actual persisted edits, valid KPI recomputation, evidence-backed prebuilt survey result, safe guided demonstrations and architectural overview. Stop here if the interview deadline arrives.
- **PR 4–7 (12 commits):** expand to full operational CRUD, Excel import, all analytical/reporting domains, survey generation and AI workflows, weighting and governance, forecasting, data architecture and full release hardening.
- A PR is the unit of review/merge; the commit is the unit of AI coding context. **One current PR branch at a time.** Each new PR branch starts from freshly pulled `main`, not from the previous unmerged feature branch. Prefer squash merges to keep `main` readable.
- A partially complete feature must stay disabled or explicitly marked as planned; never display fake interactive controls that imply successful persistence.
- Required local check before each PR: `task ci` (plus targeted tests and `git diff --check`). The five GitHub CI jobs remain `project`, `backend`, `frontend`, `rag`, `docker`; do not delete or weaken them.

### Release gates

| Gate | Requirement | State | Evidence |
|---|---|---|---|
| G0 — Planning | Canonical v1.2 located; status and dependency map agreed | DONE | Sections 0–2 |
| G1 — Security | Firebase and explicit Workforce grant enforced on all protected interfaces, including direct Render | IN PROGRESS | Both local hosts enforce grants and revocation with Firebase emulators. Hosted verification pending. |
| G2 — Dataset | Independent SQLite lifecycle, consistent seeded history, tests and audited mutations | DONE | Commits 04–06 and local `task ci` |
| G3 — Interview MVP | 90-second and 5-minute flows pass end-to-end without live AI | IN PROGRESS | Local browser walkthroughs complete. Hosted acceptance pending. |
| G4 — Full function | Operational, analytical and People Voice/AI requirements verified | PLANNED | — |
| G5 — Release | Security, accessibility, CI, hosted preview, production and cold-start smoke validated | PLANNED | — |

**Do not confuse:** passing Firebase login tests with passing project-grant authorization tests; passing `task ci` with a successful deployment; an AI-labelled result with an analyst-approved Gold finding; cancelling a vacancy with filling substantive WTE.

---

## 2. Seven PRs / 21 commit implementation plan

### PR 1 — Platform integration and protected project shell

**Branch:** `feat/workforce-intelligence-foundation`  
**Goal:** register a new independent portfolio application with protected routing and proven cross-host authorization, before exposing business records.  
**Spec:** §§3–6, 16.1, 22–24, 27.11; Appendix B; shared Portfolio Lab TRS/ADR.  
**Dependency:** latest shared Firebase session foundation; minimal reusable project-grant verification.

#### Commit 01 — Project registration, skeleton and architecture guard

`🧱 feat(workforce): register isolated portfolio module and app routes`

- Register `workforce_intelligence` in canonical project registry and create `project.json` with `/portfolio/workforce-intelligence` and `/api/workforce`; initially invisible/disabled.
- Add host-owned `/portfolio` catalogue adapter (do not change the existing `/fleet-vor-hub` URL) and thin Workforce Next.js + FastAPI entry points.
- Scaffold project-owned frontend and backend packages according to current host packaging/build configuration; do not precreate dozens of unused database tables.
- Add scoped style tokens informed by Fleet palette without importing Fleet modules or CSS.
- Extend project registry/import/CSS/packaging checks, fix specification path metadata and link canonical spec from project README.
- Tests: manifest/registry schema, host build/imports, route absence when disabled, Fleet and public-site regression.

#### Commit 02 — Shared project grant and secure BFF transport

`🔐 feat(authz): enforce explicit Workforce project membership`

- Reuse or implement the **small shared Portfolio Lab grant-verification contract** (not a Workforce-only access store), Firestore authoritative lookup, deny-by-default, revocation and mapping to one Workforce `Member` capability.
- Resolve and document the one-level/reset mapping: uniform project-scoped `Admin`-capable grant, without giving any Member global Owner authority. Prefer a shared authorization API, not host-private project imports.
- Reuse existing Firebase email/password session and same-origin Next.js BFF pattern; preserve `/api/*` rewrite, public SSE, and direct Render authorization checks.
- Ensure missing/malformed credentials, non-member UID, expired/revoked grants, Firestore outage and forged identity cannot return project data. No trust in browser-supplied email, role or project ID.
- Provide the narrowest operational way to grant a known UID access (existing platform tooling or an auditable Owner-only CLI). Do not build the complete Owner Console as part of Workforce.
- Tests: allow/deny matrix at page, BFF and direct Render, IAM/rules behavior, grant revoke, concurrent stale sessions, no cross-project access.

#### Commit 03 — SPA shell, membership UX and feature controls

`🧭 feat(workforce): add protected SPA shell and navigation`

- Implement four modes: Workforce Management, Workforce Intelligence (default), People Voice, Data Architecture.
- Internal navigation and filter state without full document reload; reload/deep-link state where safe; responsive layout, theme toggle, accessible focus/keyboard navigation.
- Project switch remains private until membership security passes; show honest `Not yet implemented` states for incomplete full-PoC sections.
- Unified loading, permission-denied, error, cold-start and demo-reset notices. Do not introduce a second login screen or hierarchy of project users.
- Tests: auth redirects, protected deep links, SPA transitions, accessibility smoke, keyboard focus, both themes.

**PR 1 acceptance:** a credential-only user without an explicit Workforce grant cannot view UI/data or call the API, even through Render; permitted participant can enter the shell; all unrelated modules still work. Host RBAC changes must be documented and tested as shared-platform work, not hidden inside project domain logic.  
**PR 1 deliverable:** protected shell only; **not** a released analytical product.

### PR 2 — Deterministic operational model and governed KPI API

**Branch:** `feat/workforce-intelligence-data-core`  
**Goal:** deliver correct source-of-truth data and calculation semantics independently of presentation.  
**Spec:** §§7–10, 16–17, 19, 27.1, 27.3–27.4, 28.

#### Commit 04 — SQLite ownership, migrations and events

`🗄️ feat(workforce-db): establish isolated schema and temporal history`

- Independent SQLite connection, DB path, bootstrap, migrations, foreign keys and explicit transactional lifetime; no Fleet DB code imports.
- Minimal MVP tables for employee, contract/assignment, establishment/position, vacancy, application, stages, offer, starter, event audit, plus revision/epoch metadata; add broader model later.
- Effective-dated contract/assignment history, stable IDs, optimistic conflict checks and audit actor UID/correlation ID.
- Deterministic reset with single-project lock and client-visible `dataset_generation`; pending simultaneous import/reset is serialized or rejected safely.
- Tests: migrations, FK integrity, point-in-time history, concurrent update rejection, data reset, Fleet isolation and startup failure isolation.

#### Commit 05 — Repeatable synthetic baseline and data contracts

`🌱 feat(workforce-data): seed repeatable recruitment scenarios`

- Versioned generation seed, `as_of_date`, scenario code and controlled synthetic workforce/recruitment events. MVP-sized data only; prepare scaling strategy for ~4,400 staff and 36 months in PR 4.
- Provide a coherent filled-vs-cancelled vacancy case, accepted-offer-vs-start case, and an FTE mutation with a predictable effect.
- Maintain required synthetic provenance, approved source inventory and fictional featured-people metadata; no real addresses, private identities or real HR data.
- Write source contracts and test fixtures; test that rerunning same seed yields identical KPI inputs without hard-coding unrelated business outputs.

#### Commit 06 — Canonical metrics, projections and API contracts

`📊 feat(workforce-analytics): calculate reconciled recruitment KPIs`

- Build approved source → Bronze → Silver → Gold **actual computations/views**, starting with the MVP outputs; do not create merely decorative layers.
- Implement canonical metric catalogue and tested executive metrics: vacancies, vacancy WTE, establishment gap, starters, median time to hire, offer acceptance and application-stage funnel.
- Separate vacancy lifecycle grain from application grain; cancellations cannot masquerade as substantive fills; use valid denominators/time-cohort definitions.
- Expose typed Pydantic `GET` and approved mutation routes with consistent `as_of_date`, refresh, data-quality and zero-denominator status.
- Tests: golden fixture calculations, cancellation/fill, effective-dated WTE, stage conversion, protected API, open vs absent data (`N/A` not zero).

**PR 2 acceptance:** real mutations persist and recalculate Gold; historical and current views reconcile; no app UI may invent KPI numbers; the 90-second path has a working backend.

### PR 3 — Interview MVP user experience and resilient demo

**Branch:** `feat/workforce-intelligence-interview-mvp`  
**Goal:** a reliable online 90-second/5-minute interview walkthrough, independent of external AI availability.  
**Spec:** §§6, 8–9, 11–13, 16, 26, 27.1/27.5/27.9/27.10–27.12, 30.1.

#### Commit 07 — Executive dashboard and one editable vertical slice

`🖥️ feat(workforce-ui): connect executive dashboards to live metrics`

- Working executive overview, KPI definitions/tooltips, filters, valid candidate funnel and simple recruiting/establishment panels.
- A controlled edit (contract FTE or recruitment stage/start event) persists through FastAPI and updates the affected KPI without a page refresh.
- Optimistic refresh/stale generation detection, safe `Not available`/`Suppressed` states, accessible data views and light/dark validation.
- Tests: browser mutation→audit→metric update, navigation and empty/failing-data behavior.

#### Commit 08 — Pre-reviewed People Voice and controlled Insight Pilot

`🧠 feat(workforce-insights): add reviewed survey evidence and pilot intents`

- Ship one deterministic **prebuilt, human-reviewed synthetic survey report** with evidence response IDs and a published Gold finding; no external API required to view it.
- Build evidence-to-response links, explicit draft/review/published separation, required safety/disclaimer copy and project-local audit.
- Implement at least one Insight Pilot **controlled intent** based on approved backend metric query; no free-form unvalidated SQL or invented numeric outputs.
- Implement Architecture Overview showing the actual project's operational/Bronze/Silver/Gold lineage and data ownership.
- Tests: invalid evidence rejected, draft excluded from Gold, reproducible approved report, allowed assistant intent and safe failure.

#### Commit 09 — Guided interview flow and MVP release evidence

`🧪 feat(workforce-demo): finish repeatable interview walkthrough`

- Guided 90-second and five-minute routes, deterministic seed/reset, stable navigation and chosen filter/date setup; do not fake actions or KPIs.
- Explicitly mark unfinished Full PoC functionality as planned; hide unsafe operations by a feature flag until tests pass.
- Add operator runbook, scripted demonstration, cold-start/fallback instructions, MVP screenshots and known limitations.
- Run local `task ci`, all GitHub CI jobs and isolated hosted checks: login, granted access, direct Render denial without grant, one edit→KPI, prebuilt report, reset and Fleet/public-site smoke.

**PR 3 acceptance = Interview MVP definition of done (spec §30.1).** If interview timing is critical, deploy this stable slice before attempting the next four PRs. Record exact deployed commit and tested environment; keep real OAuth providers deferred.

### PR 4 — Complete operational workflows and Excel I/O

**Branch:** `feat/workforce-intelligence-operations`  
**Goal:** finish controlled source data creation/import and reproducible full-scale synthetic operations.  
**Spec:** §§7–8, 17–18, 19, 27.2/27.4, Full PoC Phase 1.

#### Commit 10 — Operational entities and validated state transitions

`👥 feat(workforce-ops): complete employment and recruitment lifecycle`

- Incremental migrations and workflows for full employees/contracts/assignments, role/location reference values, vacancies, applications, interview, offer, pre-employment checks, starters, learning/PDR, promotion, probation and leavers.
- Explicit application and vacancy state machines, over-establishment flags, audit, effective dates, validations, and no physical employee deletion via UI.
- Tests: state transitions, invariants, temporal history and linked events.

#### Commit 11 — Large synthetic baseline and reconciliation

`🌿 feat(workforce-data): extend deterministic population and history`

- Reproducible target population around 4,400 fictional employees, 36 months history, representative units/locations and sufficient events across KPI domains.
- Seeds include 15 featured display names via explicit flags/order, realistic but fictional variation, clear public-vs-synthetic source register and stable observed reporting periods.
- Add performance/reconciliation tests against the large fixture. Do not treat public SCAS reported values as synthetic calculated results.

#### Commit 12 — Excel preview, commit and export

`📥 feat(workforce-import): validate and transact Excel changes`

- Downloadable template; read XLSX into bounded staging; schema/type/reference validation; row-level warnings/errors; preview inserts/updates/no-ops.
- No mutation before explicit confirmation; commit in a transaction with batch ID, idempotency, audit, recalculation and clear failure rollback.
- Scoped exports with synthetic markers, limits and spreadsheet-injection escaping. Protect import/export endpoints and rate limits.
- Tests: valid/invalid files, duplicate batch/commit, rollback, injection, excessive size, reset/import race.

**PR 4 acceptance:** full source-data lifecycle and Excel workflow, with reconcilable history and bounded performance. This PR need not finish every dashboard.

### PR 5 — Complete governed workforce analytics

**Branch:** `feat/workforce-intelligence-analytics`  
**Goal:** turn the full source model into reconciled analytical products, not disconnected charts.  
**Spec:** §§9–10, 16–17, 19–20, 27.3, 27.6–27.7, Full PoC Phase 2.

#### Commit 13 — Silver/Gold model and metric catalogue completeness

`📐 feat(workforce-model): complete conformed analytical projections`

- Finish conformed dimensions, effective-date joins, snapshots, recruitment stage facts, source/quality metadata and reconciliation checks.
- Implement canonical formulas and tests for recruitment, establishment, vacancy, onboarding, retention, progression, development, attraction and equality outcomes.
- Document grain, numerator, denominator, exclusions, comparison period, ownership and interpretation for each metric.

#### Commit 14 — Full dashboard groups and drill-through

`📈 feat(workforce-reports): deliver recruitment and workforce analytics`

- Implement full executive, pipeline, attraction, retention, progression, onboarding and candidate-experience views with consistent filters and period comparisons.
- Surface drill-through and tooltips from the same backend metric contracts; clear `N/A`/`Insufficient data` handling for sparse cohorts.
- Tests: filtered totals, cohort consistency, empty periods, metric tooltip accuracy and reasonable query time.

#### Commit 15 — Data quality, equality and suppression

`🛡️ feat(workforce-assurance): enforce aggregate quality and privacy rules`

- Deliver Data Quality and Metric Catalogue views, source register and impact badges; block misleading precision when quality fails.
- Enforce minimum-group suppression server-side **before** API export, protect against filter intersections and complementary reconstruction; correct unknown/not-declared categories.
- Validate protected-characteristic aggregation and WRES contextual labels: public benchmarks remain sourced, not invented synthetic results.
- Tests: groups under threshold, reconstruction attacks, disallowed breakdowns and invalid dimension combinations.

**PR 5 acceptance:** analytical totals reconcile to operational records; confidentiality suppression is applied at the API boundary; no fake WRES results or unsupported explanations.

### PR 6 — People Voice, external AI and governed review

**Branch:** `feat/workforce-intelligence-people-voice`  
**Goal:** complete the survey-to-action pipeline with evidence integrity and human review.  
**Spec:** §§11–13, 15, 21, 27.5–27.6, 28.4, Full PoC Phase 3.

#### Commit 16 — Survey builder and synthetic response generation

`📝 feat(people-voice): implement survey campaigns and generators`

- Question bank, campaign/audience/period controls, four seed modes, versioned taxonomy and synthetic responses.
- Response/non-response measures, analysable text, theme/mention counts and evidence IDs; data never silently treated as representative.
- Tests: deterministic generation, duplicate prevention, zero-text comments and many-to-many response/theme relationships.

#### Commit 17 — Weighting, segment insights and review priority

`⚖️ feat(people-voice): calculate governed segment signals`

- Post-stratification with approved population totals, bounded weight trimming, weighted/unweighted results and effective sample size.
- Segment prevalence, prevalence ratio, time change, review-priority components, transparent versioning, association-only triangulation.
- Small-cohort suppression and nonresponse caveats; seniority/qualification never weights the truthfulness or human value of opinions.
- Tests: reference calculations, zero denominators, suppression across filters and explainable prioritisation overrides.

#### Commit 18 — AI provider, human review and actions

`🤖 feat(people-voice): validate AI evidence and review workflow`

- Use the existing **server-side external AI connector** behind a project-owned adapter; no browser key. Structured Pydantic output, taxonomy and evidence-ID validation; reject fabricated IDs, count mismatches and unsupported findings.
- Versioned draft→review→confirmed/amended/rejected→published lifecycle; only explicitly human-reviewed findings enter Gold. Serious signals require human priority review, not automatic personnel actions.
- Two on-demand demonstration reports, fallback to prebuilt reviewed report when AI fails, full review/audit chain, management action tracker and additional controlled Insight Pilot intents.
- Tests: labelled synthetic evaluation set, malformed AI output, redaction, failures/timeouts, retries/idempotency, publishing gate and source traceability.

**PR 6 acceptance:** complete People Voice analytical workflow; AI is classification assistance, never an autonomous evidence or HR decision-maker.

### PR 7 — Forecasting, architecture and full release hardening

**Branch:** `codex/workforce-intelligence-release`

**Goal:** finish forecasting/architecture and satisfy full acceptance, including production resilience.  
**Spec:** §§14–16, 21, 24–30, Full PoC Phases 4–5.

#### Commit 19 — Baseline-tested forecasting and scenarios

`🔮 feat(workforce-forecast): add transparent forecast and what-if models`

- Historical/forecast separation, seasonal-naive baseline, appropriately validated smoothing/trend alternatives, uncertainty and methodological limitations.
- Scenario inputs for recruitment throughput, offer acceptance, time-to-start, attrition and establishment gap; no operational ambulance forecasting.
- Tests: baseline comparison, insufficient-history refusal, determinism, date boundaries and no bogus confidence claims.

#### Commit 20 — Data Architecture explorer and BPMN

`🗺️ feat(workforce-architecture): expose lineage model and BPMN`

- Expand operational/Bronze/Silver/Gold explorer, star schema, lineage, quality, sources, model diagram and zoomable People Voice→Action BPMN.
- Diagrams reflect **implemented** tables and transformations; clearly label conceptual/future relationships. Include happy and error paths, human review and action closure.
- Tests: metadata links, screen accessibility and integrity of shown lineage anchors.

#### Commit 21 — Hardening, deployment and evidence

`✅ test(workforce): verify full PoC security and release readiness`

- Complete resilience/concurrency/error-path checks, accessibility and responsive passes, cold start, performance/indexing and production authorization tests.
- Validate the Workforce password session, negative direct Render routes, public site and Fleet transport. Run all five GitHub CI jobs for the existing host and project checks.
- Finish README, deployment/runbook, current source register, canonical specification links, final test evidence and Full PoC checklist.
- Rollout only after security and smoke gates pass; document precise working status and rollback/feature-off procedure.

**PR 7 acceptance = Full PoC definition of done (§30.2).** No release claim without tested hosted behaviour.

---

## 3. Execution tracker — update at every completed commit

Status vocabulary: `NOT STARTED` → `IN PROGRESS` → `DONE` or `BLOCKED`; `MERGED` applies to the PR. Replace placeholders with factual evidence only.

| PR | Commits | Scope | Status | PR URL | Merge SHA |
|---|---:|---|---|---|---|
| PR 1 | 01–03 | Integration, explicit grant, protected SPA | MERGED | [#245](https://github.com/AlexTymosh/alextym.com/pull/245) | `a49f01b828dba84193200e39f9a09a4e92e0e14b` |
| PR 2 | 04–06 | SQLite, seed, source→Gold metrics | MERGED | [#246](https://github.com/AlexTymosh/alextym.com/pull/246) | `d2c6be784aaa612b83af2ca0f1809f8d97967c34` |
| PR 3 | 07–09 | Executive UI, reviewed survey, Interview MVP | MERGED | [#247](https://github.com/AlexTymosh/alextym.com/pull/247) | `2555f2f25b690479eb2aad2df58d6b77f8e87293` |
| PR 4 | 10–12 | Full operational flows, 4,400 seed, Excel | MERGED | [#248](https://github.com/AlexTymosh/alextym.com/pull/248) | `c47c7d5aa216ce64387898bfe77af233f49fa6dc` |
| PR 5 | 13–15 | Full workforce analytics and assurance | MERGED | [#249](https://github.com/AlexTymosh/alextym.com/pull/249) | `02bb1bea1e2a403813cb219f7e76379db58db4e2` |
| PR 6 | 16–18 | Surveys, weighting, external AI and review | MERGED | [#250](https://github.com/AlexTymosh/alextym.com/pull/250) | `68fa6ee9959a529a29d239da1feece1f221f2c29` |
| PR 7 | 19–21 | Forecasts, diagrams, production hardening | MERGED | [#253](https://github.com/AlexTymosh/alextym.com/pull/253) | `719b13f95f6567527fd7f189a78b41e11bebe1fe` |

| # | State | Commit SHA | Verification notes |
|---:|---|---|---|
| 01 | DONE | b13da5719b8baa36a14842d7bab2c8da5d5726a5 | Local `task ci`: PASS (reported); hosted CI not independently verified |
| 02 | DONE | 8d940ea06ed8285ee31bc5068278a8f69d8226bf | User-reported local `task ci`: PASS; hosted Firebase/Firestore grant verification remains outstanding |
| 03 | DONE | b100c0a18bf856586519e246ce7792d2d40e3d0e | User-reported `task ci`: PASS; local SPA opened; protected API connectivity and hosted grants pending |
| 04 | DONE | `ac4d9730b99cc849b487d12b341c409997bad705` | Eight SQLite, concurrency, reset and isolation tests passed. Ruff passed. |
| 05 | DONE | `b257cae1025ffcc020cae89db68adbdaac226594` | 11 project tests passed, including source comparison across two fresh files and reset. |
| 06 | DONE | `1fdebfe8149ed7c85d3c86e7fe06abdce86def58` | Mutation-to-KPI, HTTP authorization, OpenAPI, and BFF checks passed. |
| 07 | DONE | `7201ebc438813ded5e9ef339f827966231b60989` | Browser sign-in, FTE edit, KPI refresh and reload passed against local Firebase emulators and SQLite. |
| 08 | DONE | `fdc80cf50e05831d9bdbd0fa98d54adad94071c8` | Existing-data migration, evidence validation and exclusion of drafts tested. Real local browser verified the report, Insight Pilot and architecture. |
| 09 | DONE | `cb702dfa9d0c71ab96e43c4d1fd5fd41751680f5` | Guided navigation, reset, screenshots and local acceptance. |
| 10 | DONE | `7e2338474cbb49b692bba66068e71e96b699a1b4` | Workforce API and host checks: 24 passed. Frontend typecheck passed. |
| 11 | DONE | `817ec589443e6fc79f1d0e6e07ef22df4909831f` | 4,400-person fixture reconciled across 36 month ends; Workforce API and host checks: 27 passed. |
| 12 | DONE | `4866a1da0f86288e35327f896855d04d88d36057` | Scoped XLSX, 35 focused tests and six emulator-backed Chromium scenarios passed (project records). |
| 13 | DONE | PR #249 squash merge | Conformed dimensions, facts and reconciled outcomes. |
| 14 | DONE | PR #249 squash merge | Recruitment sources, workforce outcomes, history and vacancy dashboards. |
| 15 | DONE | PR #249 squash merge | Assurance register and inclusive recruitment. |
| 16 | DONE | `8f38dae8a73098eef7f9ff60ce57f977e3edbf49` | Campaigns, question bank, audience snapshots and reproducible synthetic samples. |
| 17 | DONE | `8f38dae8a73098eef7f9ff60ce57f977e3edbf49` | Weighted/unweighted metrics, effective sample size, suppression, review priority and linked indicators. |
| 18 | DONE | `8f38dae8a73098eef7f9ff60ce57f977e3edbf49` | Validated evidence and manual decisions, publication and action tracking. |
| 19 | DONE | `f436cdeeb447a0d4c51caf107054b971f746a87b` | Tested monthly cutoff, model holdout, reproducible runs, insufficient history, stale revisions and what-if flows. |
| 20 | DONE | `516a5d96c7c47bd8a6c6e1bcbe1c52dc701dccd5` | Same-snapshot layer examples and Gold reconciliation, model relationships and interactive process. |
| 21 | DONE | `2162f2cdf216ddb45a11f00f5afa6ec599e57b6a` plus review fix | Three interview guides, prepared candidate report, safe run logs, updated runbook and production-build campaign-switch regression test. |

### Latest checkpoint (fill after every coding session)

- **Current branch** `codex/workforce-standalone-directory`.
- **Base `main`** `719b13f95f6567527fd7f189a78b41e11bebe1fe`, merged PR #253.
- **Current scope** The Workforce route fills the viewport and uses the supplied emblem. Migration 12 applies the featured directory order and updates legacy generated aliases in place. The short fixture adds three bank contracts. The full fixture retains 4,400 employee records.
- **Current checks** 84 Workforce and host tests and 14 Chromium checks passed, including the migration, first 20 directory entries and standalone production build.
- **Interview guide** Use the short fixture for the 90-second run and the full controlled 36-month fixture to show the plotted forecast. [Interview runbook](docs/interview-runbook.md)
- **Local verification** 994 tests passed with four opt-in skips. All 15 password-demo Chromium checks passed on the Next.js production build with a local HTTPS backend. They cover Excel, campaign switching, manual publication, full-fixture planning and the mobile BPMN walkthrough. Another 34 desktop/mobile checks covered a disabled Workforce flag, public catalogue and route guards. TypeScript, Ruff and scoped Workforce lint passed.
- **Local latency sample** During the browser run, executive requests took 20–166 ms, workforce trend took 17–151 ms, forecast runs took 32–48 ms and the full controlled fixture loaded in 701 ms at FastAPI. These measurements cover local backend time.
- **Current production smoke, 16 November** The public catalogue included both projects, the Workforce gate and public site routes responded, and Render liveness returned 200. Workforce data returned 401 without a session at both the site and Render. The same-origin invalid password probe returned `401 Incorrect password`. This was a smoke check of the deployed baseline.
- **Release gate** The owner merges after review. Verify the exact deployed revision with a valid demo password and measure the warm hosted paths. This branch uses the current signed password session. Firebase remains deferred.

#### 2026-11-15 — Commit 04: isolated SQLite and temporal history

- Added project-owned SQLite migrations, ownership marker, half-open effective dates, transactional reset, and audited FTE changes.
- The database tests cover concurrent bootstrap and writes, stale versions, rollback, foreign keys, and isolation from an unrelated SQLite file.
- The runtime path is `.tmp/workforce/workforce.sqlite3` relative to the FastAPI working directory. Commands serialize through SQLite; the dataset UUID and numeric generation detect storage loss and reset.

#### 2026-11-15 — Commit 05: controlled synthetic baseline

- `interview-core` creates 15 ordered fictional Featured people and two actual starters. A separate accepted offer is ready for the actual-start action. The seed includes cancelled, administratively closed and partially filled vacancies, a repeated stage event and effective-dated contract history.
- The source register distinguishes public context from the seed's synthetic people, locations and numerical results.
- Repeatability and source reconciliation tests passed. The full-size historical population remains scheduled for PR 4.

#### 2026-11-15 — Commit 06: canonical metrics and protected API

- Exposed typed executive, vacancy, application and data quality queries and versioned FTE, cancellation, actual start and reset requests. Next.js forwards only documented Workforce paths after the access check and verifies the Origin for writes.
- Tested an effective 0.2 FTE change, cancellation without a WTE gain, and a valid actual start that increases substantive WTE. Also tested reset replay, stale tabs, refused direct access and continued host liveness after a Workforce SQLite failure.
- The MVP uses date filters, vacancy filtering for the funnel, one contract and one assignment per date, and a disposable fixed seed. The operational UI and hosted acceptance remain in PR 3.

#### 2026-11-15 — Commit 07: executive UI and effective FTE

- The two operational modes use the authenticated same-origin APIs. The dashboard combines snapshots only when the dataset ID, generation and revision match.
- Chromium used the real Lab email/password UI against the local Firebase emulators and saved FTE through Next.js and FastAPI. SQLite recorded the audit event. The dashboard changed without a document reload and persisted after one.
- The same test verified the metric definition and an empty reporting period. The development-only offline preview still makes zero protected requests.

#### 2026-11-15 — Commit 08: evidence-linked People Voice and Insight Pilot

- Added a reproducible fallback report with six linked findings excerpts, a separate published review record, an unpublished draft and a linked management action.
- Tests verify evidence IDs, rejected cross-survey or missing evidence and draft exclusion from the Gold view. Migration into an existing database preserves FTE changes and their audit.
- Insight Pilot returns the executive vacancy-rate observation for one controlled intent. Data Architecture shows implemented lineage, diagnostic results and the backend metric catalogue.
- The browser test signed in to the emulator-backed hosts and confirmed the fallback report, evidence links, vacancy-rate answer and actual lineage.

#### 2026-11-15 — Commit 09: guided walkthroughs and reset

- Added both shareable walkthroughs, a scoped reset confirmation, stale generation detection and a local emulator Member fixture. The 90-second flow edits the original SQLite record and displays the updated KPI. The longer flow reaches the application funnel, evidence report, Insight Pilot and lineage.
- Chromium verified both guides, same-session denial through Next.js and direct FastAPI after revoking the emulator grant, and a stale tab reloading after reset. The authenticated desktop captures accompany the runbook. The mobile light-mode view fit a 390px viewport.
- The hosted acceptance check remains pending on the existing dev hosts. The report labels the fixture review explicitly. A live analyst decision and on-demand analysis remain later stages.

#### 2026-11-15 — Commit 10: operational workflows

- Added typed, revision-checked source commands and Member UI for effective employment, recruitment, development, references, probation, leavers and audit.
- Historical migration preserves older source facts. Tests cover closing effective periods, ordered recruitment, an over-establishment exception, no Gold gain from a conditional/accepted offer, and stale requests.
- Focused Workforce and host tests passed (24). Frontend typecheck passed. Scale and Excel remain the next two commits.

#### 2026-11-15 — Commit 11: full synthetic dataset

- Added a confirmed shared-fixture switch with controlled and exploratory seeds. Reset still recovers the compact interview fixture.
- Added 4,400 fictional employee records, 15 people explicitly featured, 36 locations, 12 service areas, 27 role families and 36 months of synthetic operations and listening. The source register distinguishes public scale and reach from these proxies.
- Focused Workforce tests reconcile month-end WTE and starters to source, check trial reproducibility and document bounded runtime.

#### 2026-11-15 — Commit 12: protected Excel workbook workflow

- Shipped a 13-sheet template, bounded XLSX parsing, row-level preview and scoped exports. Uploads are checked on a separate copy of the source snapshot. Confirmed batches apply once under the writer lock and return the same receipt on retry.
- Tests cover the preview-to-Gold contract, row errors, duplicate submission, transaction rollback, injection, file limits, cross-Member batch isolation and racing reset. Chromium verified the real Next.js/FastAPI file path, explicit confirmation and origin/grant errors against local emulators.
- Detailed workbook keys and boundaries are in the [Excel guide](docs/workbooks.md).

### Per-commit entry template

Copy one short record below after every commit (do not replace old records):

```markdown
#### YYYY-MM-DD — Commit NN: subject
- Branch / SHA:
- Implemented: (concrete files/contracts; no claims beyond merged diff)
- Tests run: (exact commands and results)
- Functional smoke:
- Security/regression impact:
- Remaining issues and deviations from plan:
- Next commit and dependency:
```

### Per-PR sign-off template

```markdown
#### PR N — Sign-off
- Branch / PR link / head SHA:
- Diff summary and altered external contracts:
- Security and privacy review:
- Local `task ci`: PASS/FAIL (evidence)
- GitHub CI five jobs: PASS/FAIL (link)
- Hosted preview: PASS/FAIL / NOT RUN (URL, commit)
- Production smoke: PASS/FAIL / NOT APPLICABLE (URL, commit)
- Fleet + public website regressions: PASS/FAIL
- Documentation updated:
- Deployment feature flag and rollback:
- Merged SHA/date (only after merge):
```

---

## 4. Cross-cutting engineering controls

### Ownership and dependency constraints

- `frontend/app/portfolio/*` is a thin **website adapter**. All Workforce pages, components, styles and business navigation live under its project-owned frontend.
- `backend/app/main.py` mounts only the project's **public router/optional bootstrap**. Routes remain thin; application services own use cases; domain services own invariants; repository adapters own SQLite.
- Shared identity/grant logic remains in Portfolio Lab's host security layer, not duplicated in Workforce or copied from Fleet.
- `workforce_intelligence` must not import `fleet_hub`, Fleet runtime state, Fleet CSS, Fleet fixtures or its SQLite connection.
- Authentication is not authorization. An identity-only `GET /api/lab/identity` result must not be accepted as a project grant.
- A client-provided `Authorization` header is never trusted without cryptographic verification, current admission and **current project grant**.
- BFF routes must have fixed backend targets, preserve relevant headers/correlation IDs safely, handle timeouts, avoid leaking credentials and not proxy arbitrary URLs.

### Data, metrics and privacy

- Define source-event grain before UI charts. Use contract/assignment effective dates and separate vacancy requisition, positions and applications.
- Prove key KPI formulas against small golden test cases, then verify aggregates over the larger deterministic fixture.
- Use controlled response identifiers and redaction before any external AI call. Do not log free-text contents or send real workforce data.
- Restrict raw/row-level detail even in a synthetic demo when suppression is part of the governed analytical story. Suppression must occur in API responses, not only in hidden UI cells.
- Every published survey finding must reference valid evidence and a distinct explicit member review action; prebuilt reports need seeded review evidence.
- Successful reset must not destroy central Firebase identities/grants or another project's database. A project-local audit can reset with the dataset; central security events must remain durable.

### Testing minimums

- **Per commit:** focused new unit/integration tests, formatting/lint/type checks relevant to altered code, diff hygiene.
- **Per PR:** `task ci` + project-specific tests + negative auth paths + all five CI jobs before merge. Run actual browser E2E for a user-visible PR.
- **PR 1 and every release:** tests for ungranted-but-authenticated UID, wrong-project UID, revoked membership, expired session, missing Firestore, forged credential, direct Render request, client/BFF mismatch.
- **PR 2–5:** independent SQLite migrations/reset, audit and concurrency, no cross-project coupling; line-item KPI reconciliation and suppressed API results.
- **PR 6:** AI contract validation with synthetic labelled corpus; no invented response IDs or unsupported published evidence; fallback on provider unavailability.
- **PR 3/7:** record hosted tests by exact commit and environment, including deployment switches and a safe rollback.

### Important prerequisites / decisions to revalidate during PR 1

1. Current `main` could have progressed beyond Firebase identity PR #244; verify current RBAC APIs and avoid competing implementation.
2. Confirm project registry validator and packaging entry-point formats before introducing manifest, TS alias or backend dependency.
3. Confirm catalogue visibility policy and whether `/portfolio` already exists. Never auto-grant other project members.
4. Resolve the **single Member + reset capability** mapping consistently with the global access TRS. Project-scoped `Admin` grant is recommended under the existing access matrix; do not call Members global Owners.
5. Check whether all project members may reset one shared dataset. The approved spec says yes; protect with explicit warning, concurrency lock, audit, rate limit and generation invalidation.
6. Correct only the specification's out-of-date path/authorization footnotes; substantive changes require an ADR/spec amendment before code relies on them.
7. Confirm whether shared Owner tooling can provision a UID and project grant by a safe server-only command. Manual email is handled outside this application; no automatic invitation email is required.
8. Preserve the present `frontend/next.config.mjs` rewrites and the disabled-by-default Lab flow until negative tests pass.

---

## 5. Git workflow, branch naming and PR text

**Do not keep one giant unmerged `feat/workforce-intelligence` branch for the full 21 commits.** Start with `feat/workforce-intelligence-foundation` and merge each PR sequentially. Next PR starts from latest `main`. If a single branch is absolutely required for local experimentation, it is not the recommended release process.

Suggested PowerShell commands for the first PR (run only after checking the working tree):

```powershell
git status --short
git switch main
git pull --ff-only origin main
git switch -c feat/workforce-intelligence-foundation
# Add the canonical spec and this SESSION_NOTES.md at the tracked paths.
# Implement only Commit 01; run focused checks; commit; then proceed to 02.
```

**Commit convention:** `emoji type(scope): imperative subject`, followed by optional explanatory body and trailers where needed. Exact planned subjects for all 21 commits are in §2. Do not claim tests ran unless they ran.

**Reusable PR description (fill actual evidence, do not leave false checked boxes):**

```markdown
## Summary

- Deliver <PR N outcome> for the Workforce Intelligence portfolio project.
- Maintain Fleet and public-host compatibility.

## Changes

- <Concrete implementation and contract changes>
- <Security/data handling changes>
- <Tests and documentation>

## Testing

- [ ] `task ci`
- [ ] Required GitHub CI jobs (`project`, `backend`, `frontend`, `rag`, `docker`)
- [ ] Focused project tests
- [ ] Authorization/isolation regression (when applicable)
- [ ] Hosted smoke (when applicable)

## Risks & Rollback

- Known constraints: <facts>
- Release flag: <name and enabled state>
- Rollback: disable Workforce registration/feature flag or revert PR without modifying Fleet storage.
```

**Branch sequence:**

| PR | Branch |
|---|---|
| 1 | `feat/workforce-intelligence-foundation` |
| 2 | `feat/workforce-intelligence-data-core` |
| 3 | `feat/workforce-intelligence-interview-mvp` |
| 4 | `feat/workforce-intelligence-operations` |
| 5 | `feat/workforce-intelligence-analytics` |
| 6 | `feat/workforce-intelligence-people-voice` |
| 7 | `feat/workforce-intelligence-release` |

---

## 6. AI coding-agent handoff protocol

At the start of **every** new coding session:

1. Read `portfolio/workforce_intelligence/SESSION_NOTES.md` fully, then the relevant v1.2 spec sections and current Portfolio Lab security contracts; never rely only on a previous AI chat transcript.
2. Verify `git status`, current branch, newest `main` SHA, latest completed commit/PR and recent merge context. Check for uncommitted user changes before acting.
3. State a concise intended change for **one next commit**, its acceptance tests and affected ownership boundaries; do not implement three commits in one opaque patch.
4. Implement and test that slice; report modified files and actual outputs. Keep current branch changes within the approved PR scope.
5. Commit only after verification. Update this file's tracker/checkpoint with SHA, exact tests and next task; the notes update may be in the same commit (stage it before committing) or a deliberate follow-up docs correction when necessary.
6. When a PR is ready, write an evidence-based Summary/Changes/Testing/Risks description; verify CI and merge gate. After merging, refresh `main` and begin the next PR in a new branch.
7. If blocked, record the exact blocker, verified observations, a safe Owner-only preview option where specified, and the next test. Never silently relax authentication, import boundaries, suppression or review gates to make a demo work.

### Change log

| Date | Change | Evidence / reason |
|---|---|---|
| 2026-11-14 | Created 7-PR / 21-commit planning baseline; selected separate Workforce `SESSION_NOTES.md` | Technical specification v1.2 and `main` Firebase identity checkpoint |
| 2026-11-14 | Flagged Test-vs-reset capability mismatch; propose one fixed project-scoped Admin-capable grant with uniform Workforce Member UX | Portfolio Lab access matrix and v1.2 §5 |
| 2026-11-14 | Kept canonical spec under `docs/specifications/` because that is the actual user-saved path | Avoid duplicate diverging specifications |

---

## 7. Final completion checklists

### Interview MVP (PR 3 gate)

- [ ] `/portfolio` catalogue and protected `/portfolio/workforce-intelligence` route work through existing host.
- [ ] Firebase email/password + explicit Workforce grant required, checked by Next.js **and** FastAPI direct origin.
- [x] One uniform Member experience using the shared Portfolio Lab identity.
- [x] Independent Workforce SQLite, seed, migrations, local audit and scoped reset.
- [x] Real source change updates the Gold KPI and definition. Cancellation, actual starts and application grain have tests.
- [x] Executive dashboard, seeded survey review evidence, controlled Insight Pilot and architecture overview.
- [x] Guided 90-second and five-minute flows verified locally without a live AI provider.
- [x] Working capabilities and synthetic/unofficial notices appear in the UI.
- [ ] `task ci` + GitHub CI + protected hosted smoke + Fleet/public-site regressions pass.

### Full PoC (PR 7 gate)

- [x] Operational lifecycle, complete synthetic cohort/history and Excel transaction/exports (PR 4 code and local acceptance).
- [ ] Full metric catalogue, analytics/drill-through and reconciliation, quality and confidentiality suppression.
- [x] Survey generation, representativeness, weighting, segmentation, priority and triangulation.
- [ ] External AI structured evidence validation, explicit human approval, three demonstration reports and action tracking.
- [x] Forecasting, scenario planning, architecture/lineage/BPMN and all guided modes.
- [ ] Accessibility, performance, concurrency/reset, security failure modes, production smoke and rollback tested.
- [ ] All functional sections of v1.2 accounted for; any gaps documented explicitly, not silently marked complete.

**Current overall state:** PRs 1–7 merged. The standalone workspace and synthetic directory update are in review.
