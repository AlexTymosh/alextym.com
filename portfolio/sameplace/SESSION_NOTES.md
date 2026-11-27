# SamePlace — Session notes and implementation roadmap

**Revision:** 2.0 | **Date:** 2026-11-27 | **Scope:** SamePlace only

**Status:** SP01 MERGED; SP02 CANDIDATE r01 prepared. Full local CI and hosted acceptance pending. Not activated.

Canonical path: `portfolio/sameplace/SESSION_NOTES.md`.

Requirements: [SAMEPLACE_FULL_TECHNICAL_SPECIFICATION.ru.md](docs/SAMEPLACE_FULL_TECHNICAL_SPECIFICATION.ru.md) (SP-TRS-001, 1.0-draft, 2026-11-27). The document is already committed in SP01. The Owner's latest explicit decisions override earlier proposals; record any approved requirements change in the specification and an ADR, not only in this log.

## 1. Resume here

- **Last inspected main:** `98945bc295e5988e6f4223513c023ce6b4605799` (SP01 squash merge, confirmed by GitHub read-only inspection; Vercel combined status success only). Legacy freeze source remains `1e76eaa4c0ba58ceed0e5b5615917a6ee229f777` (PR42). Do not regenerate the freeze inventory.
- **Last merged SamePlace PR:** SP01, verified on main at `98945bc295e5988e6f4223513c023ce6b4605799`. Owner reports merged; exact full CI log not provided. Both canonical requirements and session ledger present.
- **Current candidate:** SP02 r01, `sameplace-sp02-room-core-r01.zip`, branch `feat/sameplace-room-core`, exact pinned main above. Apply only to clean matching main, run focused tests, full no-Task CI and optional local Emulator. Do not activate production.
- **Current evidence:** isolated domain/HTTP/fake-storage/guard tests pass on local FastAPI 0.128.2 with mocked host identity (not locked FastAPI); real full host and provider tests pending. See latest session entry.
- **Plan:** 10 sequential implementation PRs, 46 planned logical commits (4+5+5+5+5+6+4+4+4+4). Planning estimate, not an enforced count. Documentation is included in each PR; no separate documentation-only scaffold PR. One implementation branch and ZIP candidate at a time.
- **Production:** keep SamePlace disabled until the explicit release gate. Do not disable or modify legacy Preferans, existing site features, or cloud billing to make SamePlace work.

## 2. Non-negotiable constraints

1. Room-first modular monolith inside the existing portfolio host. All user-facing SamePlace links stay under `/portfolio/sameplace`; `/api/sameplace` is its independent API namespace. Stable IDs and room links survive renaming, locale changes, and activity changes.
2. Legacy `portfolio/preferans/` is frozen. Copy/extract a new independent, versioned engine and adapter from the approved snapshot, preserve attribution and rules, never import legacy internals at runtime or modify old data. Preserve legacy route, API, tests, grants and behavior. Original history stays in legacy. New engine development is independent.
3. Reuse verified Firebase identity, not unconditional global access. Creator approval is Owner-controlled; room membership can be obtained via a valid room-scoped invitation without a global project grant. No privileges in other rooms or portfolio apps. Server authorization for HTTP, direct Render requests and WebSocket; private game projections only. Firestore browser access remains deny-all.
4. Maximum three owned rooms per approved creator; configurable capacity up to ten, reduced to verified free media capacity. Owner controls global admission. Private rooms only initially. Permanent room, optional meeting, multiple paused activities, one active activity per room initially; one active playing seat per human across rooms. All humans vote on voluntary pause; technical pause and recovery do not require the disconnected actor. Never discard paused games to save resources.
5. Role separation: Owner, room owner/chief architect, architect, moderator, DJ, activity organizer, module-defined game master, player and spectator. No automatic hidden-information access for administrators. Safe bot replacement at a module-defined boundary; score stays with seat; mixed sessions excluded from primary human rankings. Local and global rankings. No legacy history import.
6. Russian-only initial application UI; future localization scoped to SamePlace and each activity. No global locale changes. Localized source/resource filenames use `.ru.` (e.g. `messages.ru.json`); stable codes/IDs in English. See section 4 for documentation language policy.
7. Five initial scenes: old apartment, by the garage, Zhdanovsky beach in Zaporizhzhia (mat), Soviet 1990s kindergarten decorative metal boat near group pavilion, card club. No dacha or cafe. Data-driven scene/editor, reusable templates, 2–4 genuine variants where applicable. Music controller survives game/skin switches. Vega MP-122S + 50U-122S: two blocks only; Radiotehnika S-50 speakers. Spring/Vesna-212S-4 and other approved skins. Source/license verification before distribution. Background ambience is optional, not a release blocker unless explicitly approved.
8. Friends and invitations, favourites, room-only audience, presence privacy (online, location/activity, last-seen visibility); chat retention 30 days; bounded physical cleanup without billed TTL. Call friends from room with recipient selection, permanent link and a waiting message. SMS/email adapters are disabled or mock-only initially, never claim delivery; no real dispatch or cost. Internal notification/share copy when implemented.
9. Strict additional infrastructure cost GBP 0. No billing upgrade, paid credentials/services, automatic overage or hidden recurring jobs. Use existing Firestore/Render/Vercel where verified, isolate dev/preview, keep RAG stable. WebSocket event delivery and ephemeral presence avoid continuous DB polling. Owner reports PR22 incident resolved; actual current usage remains to be measured. P2P-first replaceable media provider; no mandatory camera, no remote unmute, no paid TURN/SFU without explicit change to budget. Reduce effective capacity if free video capacity cannot be validated.
10. Public rooms, commerce, external code uploads, simultaneous active activities per room and 3D worlds are future capabilities, not immediate implementation. Room/account entitlements and module version/capability contracts must allow future extension. Domino rules require separate Owner-approved module requirements before actual gameplay; no invented rules or fake playable module.

## 3. Verified host integration inventory

Source links below use the inspected immutable commit; repeat inspection at the start of each PR against the actual new base.

| Area | Evidence / implementation consequence |
|---|---|
| Portfolio registry | `portfolio/catalog/registry.json`; `scripts/check-portfolio-registry.mjs` rejects any unregistered direct project directory and requires project.json, README files for project/frontend/backend/tests and a host demo page. Merely saving this file or the specification under an unregistered directory can fail repo checks. Commit both in SP01 together with registration and scaffold; do not weaken the guard. |
| Frontend | `frontend/tsconfig.json` defines public aliases; `frontend/scripts/link-portfolio-deps.mjs` creates per-project node_modules links from one host npm install (Windows junction supported). `scripts/check-registered-project-boundaries.mjs` checks registered frontend source, relative imports confined to frontend/src, CSS Modules only, no global CSS escape. Add SamePlace through public entrypoint; test aliases and additional dependency edges rather than bypassing existing checks. |
| Backend | `backend/pyproject.toml` uses editable local uv packages, explicit pytest paths; `backend/uv.lock` and `backend/Dockerfile` must include SamePlace and any independently packaged engine before frozen uv sync. `backend/app/main.py` mounts project routers with host-owned auth adapters. No application imports from RAG or legacy internal modules. |
| Access | `backend/app/security/firebase_identity.py` verifies tokens and Lab admission; `backend/app/security/project_grants.py` has uncached project grants; `frontend/lib/portfolio-lab/project-access-server.ts` uses Lab session/project access. A generic existing guard cannot simply be applied to room-only guests without testing bootstrap. Build explicit SamePlace-specific access/redeem boundary with fail-closed checks; do not relax shared admission policies. |
| Firestore | `infra/firebase/firestore.rules` denies all direct client reads/writes; server Admin SDK needs object-level checks. Keep namespace distinct from `preferans_*` and Lab control plane. Test Emulator with synthetic identities; never use production data to prove correctness. |
| Realtime | Legacy has a single-process seat-based hub, bounded presence leases, versioned authorized projections and fallback. Reuse design lessons, not imports. New connection belongs to a room member, not a seat. One active socket per client context, no DB writes for ping/mouse/AV signalling; durable transactions for authoritative actions. |
| CI | `.github/workflows/ci.yml` has project/backend/frontend/rag/docker jobs. `task ci` uses `scripts/run-ci.mjs`: repo, config, wizard, deployment, backend, frontend, RAG, Docker. Taskfile contains explicit Ruff/compile paths; pytest paths in pyproject. Include new code/test paths, Docker, lock files, Playwright, new architecture/security gates. Preserve existing checks. |
| Cyrillic policy | `scripts/check-no-raw-cyrillic.mjs` scans tracked and new non-ignored files; accepts filenames containing `.ru.` or ending `.ru`. Use English `SESSION_NOTES.md` and technical docs; `.ru.md` for Russian requirements and `.ru.json` for localized dictionaries. No broad exception or repository-wide locale changes. |
| Legacy integration | `frontend/app/portfolio/preferans/page.tsx`, host `backend/app/security/preferans_access.py`, `portfolio/preferans/`, legacy E2E and media/realtime/config surface need freeze inventory or compatibility coverage. Distinguish immutable files from shared host interfaces which may receive additive changes. |

## 4. Mandatory documentation policy (English)

**All ongoing engineering documentation must be written in English**, including this session log, README files, architecture documentation, ADRs, API/event contracts, module developer guide, data model, operations and test evidence, PR descriptions, commit messages, technical comments/docstrings, identifiers and changelogs. Use concise, accurate English, GitHub Markdown (UTF-8, LF), ASCII filenames, relative links and stable requirement/test IDs. Use diagrams (Mermaid where useful), concrete examples and reproducible commands. Keep documentation with the implementation in the same PR; stale or missing documentation is a review defect.

The original Russian product/technical requirements file `docs/SAMEPLACE_FULL_TECHNICAL_SPECIFICATION.ru.md` remains the canonical Owner-facing requirements baseline. Russian initial UI strings, game rules/user help in Russian and translations are allowed/required in explicitly localized `.ru.*` files. Do not translate or replace the canonical requirements without Owner approval. The latest English documentation requirement overrides the illustrative `.ru.md` names for engineering documents in specification section 23.2. This language policy applies to SamePlace only, not the website or legacy modules. No personal names in project documentation; use Owner and synthetic actor IDs.

Maintain the following set incrementally, not as empty files created for their own sake:

| File (relative to SamePlace) | Initial PR | Maintenance responsibility |
|---|---|---|
| `README.md`, `frontend/README.md`, `backend/README.md`, `tests/README.md` | SP01 | Build/run/test commands and module boundaries |
| `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_PLAN.md`, `docs/TEST_STRATEGY.md` | SP01 | System context, dependencies, plan, test matrix and gates |
| `docs/LOCALIZATION.md`, `docs/adr/0001-*.md` onward | SP01 | Locale scope, decision context, alternatives, consequences, status |
| `docs/DOMAIN_MODEL.md`, `docs/SECURITY_AND_PERMISSIONS.md`, `docs/API_CONTRACT.md` | SP02 | Entities, ownership, state invariants, error codes, role and object permission matrix |
| `docs/REALTIME_AND_MEDIA.md`, `docs/RESOURCE_BUDGET.md` | SP03 | Protocol, lifecycle, quotas, degradation, measurements, no paid fallback |
| `docs/INTERIOR_ENGINE.md`, `docs/ASSET_LICENSES.md` | SP04 | Scene schema, anchors, variants, editor, provenance and audio permissions |
| `docs/ACTIVITY_SDK.md`, `docs/STATE_COMPATIBILITY.md` | SP05 | Module manifest, commands, projections, capability/version contract, lifecycle, migrations |
| `docs/PREFERANS_MIGRATION.md` | SP06 | Frozen source provenance, copied code inventory, differential test evidence, rules deviations (none without approval) |
| `docs/MEDIA_OPERATIONS.md` | SP07 | Consent, NAT tests, device capacity, moderation and provider limitations |
| `docs/BOT_POLICY.md` | SP08 | Legal inputs, safe substitution, scheduling and ranking eligibility |
| `docs/activities/domino/` | SP09 | Module architecture, Owner-approved rules reference, tests and limitations |
| `docs/RELEASE_RUNBOOK.md`, `docs/ACCEPTANCE_EVIDENCE.md`, `CHANGELOG.md` | SP10 (evidence and changelog earlier as applicable) | Release, rollback, verification, open gaps |
| `SESSION_NOTES.md` | SP01 | Update in every candidate ZIP, including corrections and merge verification |

ADR format: decision ID, date, status, context, alternatives, decision, consequences, validation, supersedes/superseded-by. Link existing decisions rather than duplicate them. API/event schema is the authoritative machine-readable contract; docs explain behavior, errors and versioning. Tests and docs reference SP-UC/T-IDs from the Russian specification. Keep a coverage matrix with `PASS`, `FAIL`, `NOT RUN`, `BLOCKED`, `NOT APPLICABLE` and concrete evidence. Do not claim full coverage just because a test file exists.

## 5. Sequential PR roadmap and logical commits

PR IDs are internal (`SP01`–`SP10`), not GitHub PR numbers. Plan is a dependency-ordered sequence, not a promise that every PR fits a particular token count. A logical commit includes its relevant tests and docs. Candidate final integration must be green; ideally every commit builds independently. Commit subjects below are proposed and must reflect actual changes; use emoji + conventional commit format when delivering the real ZIP. Never add an empty commit solely to meet the count.

### SP01 — Foundation, freeze, and host integration (4 commits)

Branch: `feat/sameplace-foundation`. Depends on approved legacy SHA and Owner authorization. No user-facing activation.

1. `feat(sameplace): register isolated application foundation` — registry/manifest, buildable private entrypoints, existing Lab guard, independent editable package, lock/Docker, alias, scoped RU shell and required README scaffold.
2. `feat(sameplace): define versioned activity and locale contracts` — validated manifest metadata, future locale tags, synthetic examples and translation/authorization tests; no playable module.
3. `test(sameplace): enforce legacy freeze and CI integration` — pinned inventory, negative Git tests, boundary and host integration checks, project ESLint, Taskfile/CI and disabled-page Playwright smoke.
4. `docs(sameplace): record requirements and SP01 handoff` — original Russian specification, English session ledger, architecture/localization/test plan/ADRs and evidence.

Exit: flag off by default, registry/hygiene/CI green, old route/API/results intact, negative freeze and boundary tests, no accidental global CSS/locale or secret changes. T-001, 062–063, 069, 077–078, 085 (as applicable to scope). Freeze must compare additions/deletions/renames as well as contents, and cover legacy-specific host adapters/tests/assets. Shared host files get compatibility tests, not a blanket hash lock. Do not freeze or format the legacy directory indiscriminately. Candidate becomes next base only after verified merge.

### SP02 — Identity, room access, ownership (5 commits)

Branch: `feat/sameplace-room-core`. Depends on SP01.

1. `feat(sameplace): define durable room and membership domain` — typed entities, stable slug mappings, versioned records and transaction ports; creator approval, capacity and ownership counters.
2. `feat(sameplace): implement scoped identity and invitation redemption` — host identity adapter, invite binding/expiry/replay, authenticated bootstrap, no privilege expansion or global bypass.
3. `feat(sameplace): implement room ownership and admission policies` — create/list/join, roles, transfer, archive/restore, concurrency and durable membership, global cap contracts.
4. `feat(sameplace): expose authorized room routes and management UI` — permanent links, invite links, management menus, private discovery; protected HTTP/BFF and direct backend.
5. `test(sameplace): verify authorization and transactional room invariants` — Emulator and negative tests, audit, revocation contract, API/domain docs.

Exit: room-only new guest cannot see any other project/room, fourth room denied even in races, owner absent entry works, archive/restore preserves data, single owner transfer. T-002–014, 069–072, 082. Full active presence/capacity race verification continues in SP03. Do not use production invitation delivery.

### SP03 — Realtime room shell and social features (5 commits)

Branch: `feat/sameplace-social-realtime`. Depends on SP02.

1. `feat(sameplace): establish room-scoped realtime transport` — verified member tickets, connection lease, reauth/revoke, ordered event versions, bounded fallback, recovery and quota guard; one socket independent of game seats.
2. `feat(sameplace): implement meetings and presence privacy` — durable room vs ephemeral meeting/connection, global concurrent admission, one identity counted once, idle cleanup, friend requests and favourites, privacy-filtered projections.
3. `feat(sameplace): implement chat and room notifications` — 30-day expiry and bounded cleanup, safe text, cursor paging, internal notice, recipient selector, SMS/email stubs and share copy, no delivery side effects.
4. `feat(sameplace): build persistent room shell and location invitations` — common menus, participant layout 2/3/4/5–10, spectators separately, accept/decline, mobile-ready shell, placeholders explicitly labelled.
5. `test(sameplace): verify realtime recovery and social privacy` — WS security, race/restart, fallback budget, multi-tab, privacy leak tests, local/Emulator and protocol evidence.

Exit: friends meet without Owner, no poll storm when empty/healthy, privacy checked on every audience projection, invitations do not auto-seat. T-013–025, 051, 062–063, 070–076, 081–082. Real provider usage still measured later; no paid metrics.

### SP04 — Data-driven interiors and persistent music (5 commits)

Branch: `feat/sameplace-interiors-music`. Depends on SP03.

1. `feat(sameplace): define scene and layout registries` — separate scene geometry, semantic anchors, surface, layout presets, modular assets and versioned templates.
2. `feat(sameplace): add initial room scenes and licensed asset variants` — five specified scenes, 2–4 real variants where applicable, source/rights registry, beach mat and boat deck, no unlicensed asset distribution; unresolved assets explicitly blocked, never claim completed visuals.
3. `feat(sameplace): implement shared room decoration editor` — move/scale/rotate/replace, draft/publish, reusable templates, revision conflict, local preferences.
4. `feat(sameplace): implement shared music and replaceable player skins` — DJ, room/local audio policy, radio/recorded source distinction, autoplay, individual volume; two-block Vega plus S-50, Spring/Vesna and approved variants; no server audio rebroadcast.
5. `test(sameplace): verify scene persistence and media independence` — scene conflicts, asset rights, touch controls, state synchronization and audio continuity; English technical docs.

Exit: scene can be changed without changing game rules; music controller independent of skin. T-047–056, 061, 080, 084–085 (game-switch cases fully verified in SP06). Actual stream availability/rights are a gate, not an assumed fact.

### SP05 — Activity SDK and authoritative game lifecycle (5 commits)

Branch: `feat/sameplace-activity-host`. Depends on SP03/SP04. This precedes full Preferans adaptation deliberately so its host contract can be tested independently.

1. `feat(sameplace): define versioned activity SDK and registry` — manifest/capabilities, independent modules, user/room entitlements, schema/version pin, public/private projections, static trusted module registry.
2. `feat(sameplace): implement activity state machine and seat locks` — create/configure/readiness/start, one active slot per room and global human lock, reservations, spectator role and organizer/game-master distinction.
3. `feat(sameplace): implement pause resume and recovery transactions` — unanimous voluntary pause, technical pause, frozen timers, immutable snapshot, idempotent actions, crash after commit, distinct activity IDs, no data deletion.
4. `feat(sameplace): implement activity shell and result lifecycle` — lazy module loading/unmount, activity submenu, repeat, result finalization and history/ranking infrastructure; explicit module authorization and capability guards.
5. `test(sameplace): exercise SDK with deterministic test activities` — small test-only module(s), never advertised as real games; concurrent commands, stale versions, reconnect, two independent paused activities, contract tests, SDK docs.

Exit: generic lifecycle works without importing any legacy or Preferans-specific domain; room shell not coupled to a test activity; no bogus public game. T-026–035, 038–045, 064, 066–068, 070–073 as generic contracts; Preferans-specific proof deferred SP06 and bot-specific SP08. Document chosen SDK minimalism and version compatibility strategy.

### SP06 — Independent Preferans engine and real integration (6 commits)

Branch: `feat/sameplace-preferans-engine`. Depends on SP05 and the approved freeze source. Highest regression risk; one cohesive PR with two internal checkpoints.

1. `refactor(sameplace): extract independent preferans engine from frozen source` — new package namespace, source provenance, pure domain/rules/scoring/codec, no live legacy imports or writes; no rule invention.
2. `test(sameplace): establish preferans differential and golden scenarios` — reproduce approved source cases including recent PR changes, scoring, auction, misere, passout, undo/claims, private projections; exact recorded reference inputs and deterministic outputs; compare test-only fixtures or pinned reference in isolated harness, not a production dependency.
3. `feat(sameplace): adapt preferans commands and state to activity SDK` — independent state namespace, versioned rule snapshots, timer/pause adapters, transactions, legal moves, actor views.
4. `feat(sameplace): integrate preferans table and localized game controls` — adapt existing UI into room shell, own perspective, same visual/interaction rules, module submenu, mobile touch, safe guest projections.
5. `feat(sameplace): integrate preferans session results and room continuity` — readiness/seat swaps, observers, repeated game, pause/rejoin after restart, history/ranking idempotency, room-level media continuity; no historical import.
6. `test(sameplace): verify full preferans parity and legacy isolation` — differential, Emulator, three players plus guest, mobile desktop, restart, old project smoke and freeze; document remaining UAT gaps.

Internal stop after commits 1–2: engine package and differential tests must be coherent before UI integration. Stop after commits 3–4: exercise real adapter and privacy before final scoring/history. Split into SP06A/SP06B only if context, source availability, diff size or failing integration prevents safe completion; do not merge a broken engine. Exit: original remains identical; new module provides verified parity and independent activity lifecycle. T-026–035, 039–046, 054, 061, 064, 068–073, 077–078, 083. Bot-specific cases remain SP08. Any known rule ambiguity blocks affected behavior until Owner clarification.

### SP07 — Room-wide voice and video (4 commits)

Branch: `feat/sameplace-room-media`. Depends on SP03/SP06; shared controller must survive activity switching.

1. `feat(sameplace): implement replaceable room media provider` — interface and P2P signalling, room/location channels, bounded peer lifecycle, no paid fallback.
2. `feat(sameplace): implement media consent and moderation controls` — camera/mic user gesture, explicit mute/kick/ban, privacy, track cleanup, no remote unmute; document P2P enforcement limits.
3. `feat(sameplace): integrate responsive media participant tiles` — replace static avatars, mobile policies, device selection, location transitions, separate music volume.
4. `test(sameplace): establish free media capacity and failure behavior` — mock automation plus real-network/device acceptance protocol, NAT and bandwidth tests, verified effective cap, zero-cost evidence. If real evidence unavailable, keep media disabled and mark release blocker, never claim ten supported.

Exit: T-054, 057–061, 080, 085; media survives games; failure does not break Room Core. Production capacity needs actual measurements and Owner authorization.

### SP08 — Virtual players and safe substitution (4 commits)

Branch: `feat/sameplace-virtual-players`. Depends on SP06; SP07 precedes it in default delivery order.

1. `feat(sameplace): define bounded bot actor and substitution contract` — legal actor projection, deterministic scheduling, deadline/cancellation, no AI API or hidden information.
2. `feat(sameplace): implement preferans bot strategy` — validated legal choices, bounded CPU, testable seeded behavior, difficulty only where meaningful and approved; no human identity impersonation.
3. `feat(sameplace): support reserved seats and consensual bot substitution` — technical pause recovery, replace at safe round boundary, occupancy audit, score stays with seat, mixed session unrated.
4. `test(sameplace): verify bot legality recovery and ranking exclusion` — legal moves, information isolation, restart, fairness, CPU and mixed rankings; English bot documentation.

Exit: T-027, 032, 036–038, 045, 083, 085; manual/automated play evidence, no automatic substitute without agreed procedure.

### SP09 — Domino: second independent module (4 commits)

Branch: `feat/sameplace-domino`. Depends on SP05–SP08 and a separate Owner-approved Domino rules specification. If rules are missing, stop this PR; no invention of scoring, team rules or player counts.

1. `feat(sameplace): implement approved domino domain and rules` — independent engine, legal moves, scoring, projections, saved state; deterministic tests.
2. `feat(sameplace): implement domino activity adapter and table` — module manifest, assets/layout, localized menus, capabilities, accessible touch UI.
3. `feat(sameplace): integrate domino templates and game switching` — catalog and session config, pause Preferans / play Domino / resume, observer privacy, entitlement and result handling according to declared capabilities.
4. `test(sameplace): verify second module isolation and interoperability` — no changes to Preferans engine or core rules needed to add Domino; architecture and repeated switching tests, rule evidence.

Exit: T-034–035, 041, 047, 054, 064–068, 072–073, 080, 084–085. If SDK needs a truly generic correction, document ADR, compatibility and explicit regression tests rather than pretending zero change; no Domino-specific core conditions or Preferans engine changes.

### SP10 — Release hardening and acceptance (4 commits)

Branch: `feat/sameplace-release-hardening`. Depends on all prior PRs and all outstanding release evidence.

1. `test(sameplace): complete security and cross-project regression coverage` — trace all 85 T-IDs, threat model, revoked access, data isolation, original site and frozen Preferans checks, restart/rollback drills.
2. `perf(sameplace): validate resource budgets and lifecycle cleanup` — 15–30 min then 1h and 6/8h within verified quota; 20 switches, memory/CPU, p95, DB reads/writes, RAG contention, media limits; never spend paid quota or fabricate metrics.
3. `fix(sameplace): resolve mobile and end-to-end acceptance defects` — actual phones/tablets/desktops, touch, layout, radio rights, room controls, missing locale keys, accessibility, user acceptance.
4. `docs(sameplace): finalize release evidence and operations runbook` — all gates, changelog, compatibility, emergency disable/rollback, deployment instructions; enable flags only with separate explicit Owner approval after acceptance.

Exit: all applicable T-001–085 evidenced, full local and hosted CI, actual cloud capacity/zero-cost and UAT gates, release decision explicit. If any mandatory evidence missing, status BLOCKED/NOT RUN, do not declare v1.0 or activate paid/provider settings. Merged hardening code with flags off is not a production release.

## 6. PR count rationale and stop rules

The roadmap groups by architectural dependency and risk, not by every UI control. Ten PRs and roughly 46 logical commits are a planning estimate for full private v1.0, including Domino, bots, media, editor and release evidence. A first useful closed beta with room and real Preferans is reached at SP06 (subject to gates); it is not full v1.0. Do not add speculative features to fill a planned PR.

No reliable fixed token or LOC limit guarantees context retention. Keep one active PR; maintain a short internal checklist at each logical commit. Before beginning the next checkpoint, verify current diff, changed contracts, failing tests and docs, record continuation state. If the full package cannot be safely reviewed, split only at a buildable dependency boundary; record reason, remaining tasks, and revised count. Never continue with guessed file contents or lost context. Correcting a failed candidate normally stays in the same branch/PR, with a new ZIP revision and explicit correction entry, not a new numbered stage. Never combine freeze/access, new engine extraction and media-provider activation into one giant rewrite. Avoid repetitive micro-PRs for cosmetic tweaks.

## 7. Required per-session / ZIP workflow

1. Read this file, canonical spec sections for the next stage, relevant ADRs and previous evidence. Resolve actual `main` SHA and verify previous merged PR; inspect changed files and latest legacy freeze status. Do not treat chat memory or a previous ZIP as authoritative source. Request Owner confirmation if baseline differs materially or rules are ambiguous; no programming without authorization.
2. Work on the designated fresh branch from verified main. Reconcile uncommitted local docs safely. No production secrets or data, no changes to `main` directly. Preserve protected paths and deny-all Firestore rules. Use small coherent diffs with contract/unit/integration tests first as appropriate. Reuse exact locked dependency versions. Do not silently weaken CI or format frozen legacy files.
3. Complete each planned logical commit, including relevant English docs and acceptance trace. Run focused checks as work proceeds; full `task ci` before delivery where a complete checkout is available. Ensure `CI_CHECKS` is unset (partial CI is not full CI). Include exact tool versions, test commands, environment, pass/fail/skip evidence. If no complete checkout/Emulator or no real browser devices, state that explicitly. Do not mark unchecked boxes.
4. Package a ZIP only after checking all patch anchors and protected file diffs. Name `sameplace-spNN-<scope>-rNN.zip`. Include a manifest with exact base SHA, target branch, file actions/hashes, commit groups and ZIP revision; `README.md` (install/rollback), `apply.ps1`, `verify.ps1` when appropriate, actual new/changed files or deterministic patches, and the updated `portfolio/sameplace/SESSION_NOTES.md`. Include the canonical specification if it must be installed and is not already present; do not overwrite locally edited requirements blindly. No `.env`, real UID/token, private state, node_modules, virtualenv, or production assets without provenance.
5. PowerShell scripts must be Windows-compatible, preflight all file paths/anchors/hash expectations before writes, reject wrong base/branch or conflicting working tree (explicitly permit only exact matching pre-saved documentation when expected), avoid partial application, provide rollback, and fail nonzero on errors. No automatic commit/push/merge, paid config, deployment, migrations or data deletion. Verify no path traversal and no unrelated file changes. Provide concise commands to apply, test, stage exact files and create the logical commits. No broad `git add .` or destructive `git reset --hard` in installers.
6. Every ZIP delivery includes the revised log entry with actual implemented scope, file/contract changes, tests performed, limitations, next action, and status `CANDIDATE` or `VERIFIED_LOCAL` only if evidence supports it. Include branch name, emoji conventional commit messages and PR body in English with `## Summary`, `## Changes`, `## Testing`; include squash subject/body if used. `[x] task ci` only after complete successful run; otherwise `[ ] task ci` with reason. Owner applies candidate and reports tests/merge; do not claim merge in advance.
7. After Owner confirms merge, resolve actual main and PR merge SHA, verify previous candidate is incorporated and tests/status where available. Record `MERGED` with evidence in next log update; if previous tests were not actually verified, record Owner-reported separately. Next ZIP includes prior merge confirmation and new candidate entry. Do not force a separate bookkeeping PR just to mark merge; final SP10 merge/release evidence can be supplied as a final log-only update if needed. Keep release status separate from merged code.

Recommended merge strategy: keep the 4–6 logical review commits on the feature branch; squash merge each completed PR if repository policy/Owner permits. Thus about 46 development commits on branches and 10 integrated commits on main (excluding fixes, rebase or unrelated changes). If retaining every logical commit on main is preferred, use the existing approved repository strategy instead; no automatic policy change.

## 8. Gate definitions

- **PLANNED:** scope only, no candidate.
- **CANDIDATE:** ZIP produced; list actual tests, failed/not-run checks, open defects. Not merged or released.
- **VERIFIED_LOCAL:** exact candidate applied and full `task ci` passed, evidenced by command output or explicitly attributed Owner report; scope-specific gates listed separately.
- **MERGED:** main contains verified PR merge; capture SHA/link and hosted status if available. Does not imply UAT or production release.
- **BLOCKED:** required source, rules, permissions, resources, tests or evidence missing; specify actionable next step.
- **RELEASED:** explicit Owner approval and production activation/verified smoke, all mandatory acceptance gates satisfied. Not inferred from GitHub merge or Vercel status.

Mandatory per-PR common gates: full CI, clean diff, freeze guard, unchanged site/RAG/legacy behavior, scoped i18n, no secrets or paid changes, English documentation updated, reproducible new tests, no unapproved public visibility. Scope gates in section 5 accumulate across PRs. Some end-to-end cases can only be completed after subsequent dependencies; explicitly mark partial coverage, not pass. Require final evidence for all mandatory criteria before release. Use separate dev Firebase/Emulator; do not run test writes against production. Rollback only SamePlace feature or compatible release, preserve durable data and old module decoders. Stop if quota safety uncertain.

## 9. Progress ledger

| PR | Planned commits | Status | Candidate / merge SHA | Evidence / next action |
|---|---:|---|---|---|
| SP01 | 4 | MERGED | `98945bc295e5` | Owner confirmed; main contents verified; Vercel success, full CI log not independently observed |
| SP02 | 5 | CANDIDATE r01 | `98945bc295e5` (base) | Room core implemented; full local/hosted CI and Emulator pending |
| SP03 | 5 | PLANNED | - | Depends on SP02 |
| SP04 | 5 | PLANNED | - | Depends on SP03 |
| SP05 | 5 | PLANNED | - | Depends on SP03/SP04 |
| SP06 | 6 | PLANNED | - | Depends on SP05 and frozen Preferans source |
| SP07 | 4 | PLANNED | - | Depends on SP03/SP06; capacity evidence |
| SP08 | 4 | PLANNED | - | Depends on SP06; default sequence SP07 then SP08 |
| SP09 | 4 | PLANNED | - | Requires approved Domino rules |
| SP10 | 4 | PLANNED | - | All previous stages and acceptance gates |
| **Total** | **46** | **1 merged** | - | SP02 candidate; SP03–SP10 planned |

## 10. Open items (carry forward until evidenced or resolved)

| ID | Item | Owner / gate |
|---|---|---|
| OPEN-01 | Pinned PR42 SHA in SP01; generate and verify actual inventory on apply. Owner to protect freeze guard/manifest and confirm merged baseline. | SP01 |
| OPEN-02 | Verify exact Lab identity/admission bootstrap for room-only guests, invite ownership proof and revocation; avoid generic grant bypass. | SP02 |
| OPEN-03 | Current Firestore usage, actual free quota/Render/Vercel configuration, staging isolation and current provider terms; PR22 resolved per Owner, not independently metered. | SP03, SP10 |
| OPEN-04 | Licensed scene assets, Vega two-block and S-50 appearance, radio sources/rights. | SP04 |
| OPEN-05 | Full current Preferans source/rules inventory, test parity, package migration boundary and actual three-player/mobile UAT. | SP06 |
| OPEN-06 | NAT and free AV capacity on actual devices; if lower than ten, enforce lower effective cap. No hard no-charge proof means no paid provider activation. | SP07, SP10 |
| OPEN-07 | Concrete Domino rules approved by Owner. | Before SP09 |
| OPEN-08 | Long-run resource budget, complete acceptance matrix and release/rollback evidence. | SP10 |
| OPEN-09 | SamePlace name clearance and commercial hosting/license/privacy requirements. | Future commercial launch; not private development blocker |
| OPEN-10 | SP01 r02 included in merged main; historical failure retained, full post-fix CI log not independently observed. | SP01 merged |

## 11. Session history (append; do not erase past failures)

### 2026-11-27 — planning baseline

- Reviewed canonical local SP-TRS-001 1.0-draft (1,618 lines), requirements and all 85 acceptance criteria; organized stages around actual integration boundaries rather than separate PR for every feature.
- Inspected main at `6745910cd3aeb46551cc8c59cdcf50c9220b3ba0`; legacy notes through PR41. SamePlace not registered; expected notes/spec paths returned not found. Verified existing registry, project and source boundary checks, raw Cyrillic check, host auth adapters, Firestore deny-all rules, uv/pytest and Docker paths, CI job/task structure.
- Planned 10 PRs / 46 logical commits. Moved generic activity lifecycle ahead of real Preferans extraction/integration to avoid room/game coupling; added explicit checkpoint in SP06. Documentation-only PR omitted because unregistered project directory fails current checks. Proposed squash merge per PR only if Owner/repository policy permits.
- Latest requirement: detailed ongoing engineering documentation in English; Russian canonical spec and Russian UI remain localized files, no whole-site localization. This log is English and project-local.
- No code changes, installer, ZIP, remote writes, tests, or production actions. Next: SP01 only after explicit instruction. Before SP01, verify actual main and protect latest approved source; do not assume this observed SHA remains current.

### 2026-11-27 — SP01 / candidate r01 — Foundation, freeze and host integration

- Base main SHA: `1e76eaa4c0ba58ceed0e5b5615917a6ee229f777` (PR42). Branch: `feat/sameplace-foundation`. ZIP: `sameplace-sp01-foundation-r01.zip`. Exact base blobs, payload SHA-256 digests, four commit groups and patch instructions are in the external package manifest.
- Status: CANDIDATE, not merged. Requirements: SP-TRS-001, SP01, T-001, T-062/063, T-069, T-077/078, T-085 (partial coverage only). ADR 0001 and 0002. Canonical Russian specification is preserved byte-for-byte. This ledger is updated in English, original planning history retained.
- Implemented: registered catalog-hidden SamePlace module, independent editable Python package, guarded `/api/sameplace/status` and `/portfolio/sameplace` entrypoints (exact `SAMEPLACE_ENABLED=true` and Lab/project grant required; off by default), scoped Russian dictionary and typed translator with safe fallback/plural/pseudo tests, validated versioned activity manifest metadata with independent locale tags, no runtime plugin loader. Additive host registry, aliases, packaging/lock, Docker, mount, Taskfile and CI. Host-specific authorization remains in a thin host adapter. No room/social/media/game data or actual games implemented.
- Freeze: pin PR42 Git commit, generate `docs/legacy-freeze.json` deterministically from its tree at installation. Protect all legacy-named paths outside SamePlace; compare Git tree, index, working tree, mode and hidden flags; fetch pinned commit for shallow project CI. Shared host compatibility assertions and existing regression tests retained. No legacy files modified, no history migration, no production settings. Review protection for the guard/manifest itself remains Owner responsibility; no remote tag or branch protection created.
- Focused evidence in isolated author environment: Python 3.13.5, Node 22.16.0; `pytest test_activity_manifest.py`: 20 PASS; `pytest test_foundation_api.py`: 9 PASS with a synthetic stand-in for host project-grant module and real candidate adapter/router (not actual Firebase or whole host); `node --test freeze.test.mjs`: 11 PASS using temporary Git repositories; `node --test localization.test.mjs`: 5 PASS using local TypeScript compiler. All 21 replacement anchor counts and eight expected blob SHAs were verified by GitHub read-only calls. Eight installer fixture assertions passed (exact pre-saved docs, rejection of unrelated changes, pinned tree inventory, preflight, rollback, no helper leakage, legacy unchanged and duplicate anchor rejection). Payload hashes, Cyrillic filenames and whitespace were checked. No complete repository clone available. Full Ruff, uv lock check, actual host composition/import tests, project ESLint, Next/Playwright, full RAG/Docker and hosted CI are NOT RUN; run locally. No Emulator/real-device/provider checks in SP01. Test harness and delivery helpers remain outside the repository.
- English documentation: README files, ARCHITECTURE, DEVELOPMENT_PLAN, LOCALIZATION, TEST_STRATEGY and ADRs added; Russian requirements unchanged. No global site localization, no new external dependencies, no paid features.
- Delivery: external `apply.py` / `apply.ps1` validates exact origin/main, permits only unmodified pre-saved docs, checks all anchors, creates branch, writes only manifest-listed files and generated freeze inventory. `ci-no-task.py --format --workers 2` mirrors eight local CI groups and formats only candidate Python paths; `commit-groups.py` stages exact files and creates four logical commits. Actual commit order is adjusted from planning so registry/entrypoints/build inputs are installed atomically; no artificial empty commits. Do not stage helpers or test artifacts.
- Rollback: before merge, keep feature branch for inspection or switch to clean main after safely preserving changes; do not reset or delete unrelated work. After merge, revert SP01 if necessary with SamePlace flag off. No persistent SamePlace data exists at this stage.
- Next: Owner applies r01, checks actual frozen inventory, runs full CI and reviews/merges. Capture exact merge SHA and test evidence in the next candidate update. SP02 must implement room-specific admission instead of loosening shared project grant policy. Do not start SP02 until SP01 merged and verified.

### 2026-11-27 — SP01 / candidate r02 — Host routing test correction

- Owner-reported `uv run --locked python -m pytest`: 1 failed, 1,554 passed, 8 skipped, 1 warning (63.88 s). `test_host_mounts_the_guarded_router` expected a flattened `APIRoute` inside `app.routes` and found zero. No evidence of a production route failure. Starlette TestClient deprecation warning is unrelated.
- Root cause: FastAPI 0.137 changed router inclusion to retain nested router metadata; `router.routes` is an internal implementation detail. Reference: https://fastapi.tiangolo.com/release-notes/#01370. The host dependency declaration already requires FastAPI >=0.138.1.
- Replace brittle inspection with HTTP tests against the actual host app: disabled feature (404, no identity lookup), 401/403/503 authorization propagation, successful 200 response and correct project grant scope with exactly one check, wrong method 405, and legacy route existence via an unsupported method (405, no legacy storage handler). Keep the existing dependency-direction test unchanged. No private FastAPI routing API used. No runtime application, host, dependency, legacy, or infrastructure changes.
- Author validation: six new HTTP cases passed using a synthetic composition host, actual candidate router/guard, mocked grant verification and FastAPI 0.128.2; full host, architecture test and locked dependency behavior must be checked on Owner's checkout. Full CI remains pending. Do not mark it as passed before actual evidence.
- Delivery: incremental ZIP `sameplace-sp01-foundation-r02-fix.zip` updates only `tests/test_host_integration.py` and this session log on the existing SP01 branch. Keep the original CI runner and four commit groups; no additional PR or commit required. Run focused tests then full CI, and only commit/push if green.

### 2026-11-27 — SP02 / candidate r01 — Identity, room access and ownership

- Base: `98945bc295e5988e6f4223513c023ce6b4605799`, SP01 merged as verified in GitHub. Branch `feat/sameplace-room-core`, ZIP `sameplace-sp02-room-core-r01.zip`. Five logical commits. No remote writes. Preserve canonical Russian specification, freeze source/inventory, old Preferans API and all existing provider settings.
- Implemented typed room commands, versioned aggregate and transactional port; private room catalogue, creation approval, immutable unique slug, three active rooms/owner, configured storage and capacity caps, owner-only platform limits, archive/restore, delegated roles, moderation, two-party transfer, target-bound expiring one-time invitations and idempotent redemption, neutral errors, quota circuit and bounded process-local mutation limiter. Room-only Firebase identity verifies existing record policy, new verified email account can prove identity without creating global Lab record or project grant. Route-local session, BFF and Russian UI. Firestore documents under `sameplace_room_core_v1` only on authorized mutation; no migrations, real writes or production activation.
- Requirements: T-002–012, T-069–072, T-082 partial. Active presence, simultaneous admission limits, meetings, capacity and queue (T-013/014), live revocation, favourites/recent, social chat/notification stubs belong to SP03. Interiors identifiers only, no art/editor/media. Activity/game/bot/commerce later. No payments, automatic SMS or invite email delivery.
- Decision requiring review: newly generated invitation URL uses `/portfolio/sameplace/j#<token>` to keep secret outside HTTP path/referrer logs; legacy proposed `/j/{token}` remains compatible. Explicit scoped sign-out does not clear global site session; host sign-out does not clear scoped SamePlace session. No automatic grant. Local registration explicitly sends Firebase verification email only on request. Initial policy caps 100 stored rooms, four active rooms, 20 active humans, capacity ceiling ten (the latter three are configured, not measured/enforced active capacity yet). Room owner may restore only if currently approved/within limits. Receipt/audit cleanup and privacy deletion are release gates; no paid TTL. See ADR 0003.
- Tests: isolated service, transaction adapter fake, HTTP tests on FastAPI 0.128.2, and mocked host guard tests with stand-in policy: 31 PASS, one opt-in Emulator skipped. These do not prove locked FastAPI or real Firebase behavior. JS localization and exact BFF allowlist: 6 PASS. Package hashes and installer fixture verification recorded in delivery README. Actual host tests, full CI, real Firestore/Auth Emulator, enabled UI/CSRF tests, provider logging and resource measurements NOT RUN in author environment. Owner runs complete local CI and reviews before merge. No guarantee of free AV capacity.
- English docs updated: DOMAIN_MODEL, SECURITY_AND_PERMISSIONS, API_CONTRACT, ARCHITECTURE, TEST_STRATEGY, ADR 0003 and README files. Russian UI only in localized resources, no global site changes. Keep the feature off through acceptance. No separate dependencies or lock changes; only host mount and route-local credential/BFF adapters outside project. Existing SP01 status unchanged.
- Rollback: keep flag off; revert SP02 as a unit if necessary, do not delete any room records or change freeze inventory. No persistent production data expected because no activation. Before SP03 verify actual merged main and local/hosted evidence; carry forward open Emulator/provider and admission checks.

### Template for the next candidate entry (replace placeholders; retain history)

```markdown
### YYYY-MM-DD — SPNN / candidate rNN — scope

- Base main SHA: <verified full SHA>; prior merge: <PR URL/SHA/evidence or none>.
- Branch: <branch>; ZIP: <exact name>; package manifest / revision: <hash or reference>.
- Status: CANDIDATE / VERIFIED_LOCAL / BLOCKED (not merged).
- Requirements / ADR / acceptance IDs: <IDs>.
- Implemented: <actual changes>; deferred / not implemented: <scope>.
- Files / contracts / data schema / flags: <changed paths and version implications>.
- Freeze evidence: <manifest check; protected diff; legacy regression evidence>.
- Tests: <exact commands, environment, counts, PASS/FAIL/NOT RUN, reasons>.
- Full task ci: <evidence or NOT RUN>; hosted CI: <status or NOT RUN>.
- Real-device / Emulator / usage evidence: <results or explicit limitations>.
- English documentation updated: <files>; Russian localized requirements/UI: <changes if approved>.
- Rollback / compatibility: <steps>; no paid provider or production actions unless explicitly authorized.
- Blockers / assumptions / decisions: <details and next action>.
- Next step: <one precise action, conditional on actual merge>.

### YYYY-MM-DD — SPNN merge verification / correction

- Prior candidate revision: <rNN>; result: <actual merge SHA and PR URL or failure>.
- Owner-reported versus independently verified evidence: <distinguish>.
- Correction / remaining tests: <details>; ledger updated accordingly.
- Next base: <actual verified main SHA>.
```

End of current log. Append new entries in chronological order; update the resume block and progress ledger in each package. Keep the canonical specification unchanged unless requirements are explicitly revised. If this file becomes long, move older detailed evidence into linked English stage reports under `docs/`, preserving all historical entries or links, and keep the current resume block concise.
