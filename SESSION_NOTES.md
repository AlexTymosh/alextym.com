# SESSION_NOTES — Portfolio architecture and Fleet VOR Hub migration

> **Progress (2026-10-27):** Foundation PR #208 merged to `main` at
> `fe0470e76a9c3ec479881fc0e4f7640d9566905b`. PR 2 moves only the Fleet
> frontend implementation; backend/SQLite remain untouched pending PR 3.
> The historical baseline and PR 1 instructions below are retained as
> project migration history.

**Date:** 2026-10-26
**Repository:** `AlexTymosh/alextym.com`
**Baseline:** `main` after merged PR #207 (`b4601ac534e569e80f624c70dded8297a2d2d406`)
**Suggested new chat title:** `Portfolio Architecture — Foundation & Fleet Hub Migration`
**First Git branch:** `refactor/portfolio-foundation`
**Status:** PR 1 foundation prepared as a local patch. No GitHub mutation, production change, or application code relocation performed by this patch.

## 1. Product decision (fixed unless explicitly revised)

1. `alextym.com` is always the only website. Portfolio projects are **embedded demos**; they will not be standalone repositories, websites, microservices or separately deployed apps.
2. Use a **feature-first modular monolith**: `portfolio/fleet_hub/`, `portfolio/<next_project>/`, etc. Each directory will own its own frontend, backend, demo data, tests, scripts and docs.
3. Existing Next.js (`frontend/`, Vercel) and FastAPI (`backend/`, Render Free) are shared hosts. Site adapters call the project's public entrypoint; project code never imports website business logic or other projects' internals.
4. Portfolio catalogue metadata is **not** a public page. Do not add `/portfolio`, a menu entry, or automatic route discovery in the current migration.
5. Existing Fleet demo route remains `/fleet-vor-hub`; all `/api/vor/*` paths, authentication/session/cookies and three redirect routes must remain compatible. Old v1 `/fleet-vor-hub-01` and `/api/vor-01` remain retired.
6. Preserve exact Fleet SQLite seed and existing demo functionality: 20 vehicles, 42 tickets, 219 events; record `GX24 KLM` is `Basingstoke` / `Jason W.`. Approved seed SHA-256: `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`.
7. No redesign or business-logic changes to the rest of Home, Resume, Chat, Contact, RAG, Telegram or existing case studies. Audit architectural dependencies and CSS only.

## 2. Existing architecture (verified against GitHub `main`)

- PR #207 merged on 2026-10-26; latest local demo seed and legacy v1 removal are in `main`.
- Frontend Fleet implementation: **29 files** below `frontend/app/fleet-vor-hub/`, including four Next.js page route files, components, CSS and a demo vehicle image.
- Backend Fleet: eight `backend/app/api/vor*.py` router modules plus eight `backend/app/services/vor*.py` service modules and one `vor_seed.sqlite3` (17 backend files total).
- Fleet backend tests: existing `backend/tests/test_vor*.py` and the seed contract test. Do not delete tests to satisfy CI.
- Current backend startup imports and registers eight separate Fleet routers in `backend/app/main.py`.
- Current `vor_store.py` takes `SEED_FILE` from `__file__` and the default runtime SQLite path from `__file__.parents[2] / "_local"`. Relocation changes those resolutions: explicitly preserve runtime path semantics and `VOR_DEMO_DB_PATH` during PR 3.
- Current Dockerfile copies `backend/app` and does not automatically include a root `portfolio/` directory.
- Current Next.js `turbopack.root` points at `frontend/`; Vercel is frontend-scoped. Moving TSX outside it will require conscious Next/Vercel build configuration in PR 2.
- Current `frontend/app/layout.tsx` wraps Fleet with the site's navigation and footer; CSS globals and Fleet's non-module CSS may cause style leakage.
- CI: `.github/workflows/ci.yml` runs separate project/backend/frontend/RAG/docker jobs. `Taskfile.yml`'s `repo:check` is used both locally and by the project CI job.
- Render Free filesystem is ephemeral. A new runtime SQLite file is seeded only if missing. The first PR does not change this or introduce a reset-on-every-start mode.

See `portfolio/fleet_hub/docs/migration-map.md` for detailed inventory and risk points.

## 3. Target ownership tree

```text
alextym.com/
  frontend/                             # website Next.js host
    app/fleet-vor-hub/page.tsx          # thin adapter only (eventual)
  backend/                              # website FastAPI host
    app/main.py                         # one Fleet public router registration (eventual)
  portfolio/
    README.md
    catalog/registry.json              # metadata only, no public route
    fleet_hub/
      project.json
      README.md
      frontend/                         # owned Fleet frontend, after PR 2
      backend/                          # owned Fleet API/SQLite, after PR 3
      tests/                            # owned tests, after PR 3
      docs/
      scripts/                          # if useful, after utility audit
    another_project/                   # create only when needed
  docs/architecture/portfolio.md
  scripts/check-portfolio-foundation.mjs
```

## 4. Implementation workstream — independently mergeable PRs

### PR 1 — foundation (THIS PATCH)

**Suggested branch:** `refactor/portfolio-foundation`

Add only:

- Root `SESSION_NOTES.md` (this durable handoff plan).
- `portfolio/README.md` and `docs/architecture/portfolio.md` (project ownership, dependency directions and quality gates).
- `portfolio/catalog/registry.json` and `portfolio/fleet_hub/project.json` (hidden future catalogue metadata, no route exposure).
- `portfolio/fleet_hub/{frontend,backend,tests}/README.md` (empty planned destinations, no executable code).
- `portfolio/fleet_hub/README.md`, `portfolio/fleet_hub/docs/migration-map.md` (verified migration inventory).
- `scripts/check-portfolio-foundation.mjs` (validate manifest/registry, naming, uniqueness, route existence, unpublished catalogue).
- Update **only** `Taskfile.yml` to run the checker via `portfolio:check` inside `repo:check` (and therefore existing GitHub CI).

**Do not change:** current Fleet source, seed, API, routes, Vercel/Render settings, global layout, site components or existing test expectations. Do not create a `/portfolio` page.

**Acceptance checks:**

```powershell
node scripts/check-portfolio-foundation.mjs
task portfolio:check
task repo:check
task ci
```

`task ci` must finish with all checks passed; PR project/backend/frontend/RAG/docker jobs must be green. `git diff --cached --stat` must show no SQLite/source moves. Changes in `main` after patch preparation must be reconciled before installing.

### PR 2 — frontend move

**Suggested branch:** `refactor/fleet-hub-frontend-module`

1. Record baseline browser screenshots and supported flows (login, vehicle register, dashboard, calendar, defect creation, operations, reconciliation, export).
2. Choose the smallest importable local Next.js project module under `portfolio/fleet_hub/frontend/`; configure the host to consume it. Avoid creating a separate Next site or server.
3. Move Fleet React components, local images, styles and project-only hooks into `portfolio/fleet_hub/frontend/src/` via `git mv` where possible.
4. Keep `frontend/app/fleet-vor-hub/{page.tsx,register/page.tsx,new-defect/page.tsx,process/page.tsx}` as route adapter/redirects. No domain code left there.
5. Update Next.js imports, `transpilePackages`/Turbopack root if necessary, npm lockfile/workspace as needed, and Vercel access to files outside frontend root. Keep all public URLs.
6. Scope non-module Fleet CSS (`issue-hub-redesign.css`, `operations/workflow-redesign.css`) to Fleet; ensure site CSS cannot unexpectedly style Fleet internal controls.
7. Remove Fleet reference to website profile image (or make it an explicit configuration prop), without changing the user-visible presentation unintentionally.
8. Check mobile/desktop screenshots, frontend lint/types/build/E2E, Vercel preview, full `task ci`.

**Gate:** UI, behavior and route semantics unchanged; no imports of website components from Fleet internals; production-friendly Vercel build verified.

### PR 3 — backend + data + tests move

**Suggested branch:** `refactor/fleet-hub-backend-module`

1. Record baseline OpenAPI route/method inventory, cookie path attributes, public status/response schemas and environment variables.
2. Move eight Fleet API routers, eight Fleet service modules and exact SQLite seed under `portfolio/fleet_hub/backend/` without changing business rules.
3. Expose one public Fleet router entrypoint; reduce `backend/app/main.py` to a single Fleet registration while preserving `/api/vor/*`.
4. Configure minimal Python local-path dependency or packaging and `uv.lock`, plus Dockerfile build/install of code under root `portfolio/`. No independent FastAPI service or deployment.
5. Fix all file-relative paths; preserve runtime database path contract and `VOR_DEMO_DB_PATH`. Keep seed and runtime DB separate.
6. Move Fleet tests into `portfolio/fleet_hub/tests/`, retain their CI collection, and update monkeypatch import paths only. Keep every security and delivery-allowlist regression test.
7. Audit, classify and relocate active Fleet scripts; delete obsolete patch scripts only after checking consumers.
8. Confirm fresh Render Free service uses the approved seed without accidental reseeding of an existing local writable DB. Never modify production database without a separate backup/approval.
9. Run SQLite SHA/integrity/FK tests, route snapshot contract, full backend CI, Docker smoke and deployed API smoke.

**Gate:** same routes/auth/data and no new paid infrastructure; approved SQLite seed hash unchanged; test coverage not reduced.

### PR 4 — host structure / CSS and dependency isolation

**Suggested branch:** `refactor/website-portfolio-boundaries`

1. Audit site import graph, CSS cascade and global layout. Focus on leakage, not rewriting Home/Resume/Chat/Contact.
2. If justified by screenshot comparison, separate website shell and demo shell with Next.js route groups `(website)` and `(demos)`; route groups must keep exact URLs and page metadata.
3. Add static forbidden-import checks for website -> Fleet internals and Fleet -> website business code; explicitly allow only public router/component adapter imports.
4. Add CSS namespace checks and cross-page screenshot comparisons. Protect root site routes, Chat and Contact.
5. Check sitemap/robots and no accidental `/portfolio` exposure; preserve API rewrite behavior.

**Gate:** no visible changes outside intentional shell isolation; independent CSS, imports and stable routes.

### PR 5 — finish and future Portfolio catalogue preparation

**Suggested branch:** `refactor/portfolio-architecture-audit`

1. Consolidate architecture validation in CI, verify all project code ownership under `portfolio/fleet_hub/` and no Fleet business logic left in host.
2. Keep hidden registry metadata only; do not create `/portfolio` page or navigation link unless separately approved later.
3. Audit obsolete install/check scripts and documentation references. Remove only proven dead scripts.
4. Update operational docs, baseline architecture diagram, adding-project instructions and rollback guidance.
5. Run full local and GitHub CI + end-to-end demos, Render/Vercel preview/deployment checks, SQLite integrity, routes and data.

**Gate:** zero unauthorized cross-module imports; successful production smoke after deployment; complete docs for creating `portfolio/next_project/`.

## 5. Public and data contracts that must never change implicitly

| Contract | Expected |
| --- | --- |
| Main Fleet UI | `/fleet-vor-hub` |
| Old v1 UI/API | `/fleet-vor-hub-01`, `/api/vor-01` remain retired |
| Active Fleet API | `/api/vor/*` unchanged |
| Redirects | `/fleet-vor-hub/register`, `/fleet-vor-hub/new-defect`, `/fleet-vor-hub/process` |
| Fleet demo dataset | 20 vehicles, 42 tickets, 219 events |
| Reference vehicle | `GX24 KLM` -> `Basingstoke`, `Jason W.` |
| Seed SHA-256 | `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532` |
| Render | Existing Free service, SQLite ephemeral limitations remain |
| Site SEO | Existing public routes/sitemap/robots unchanged |
| Current menu | No Portfolio link introduced |
| Other features | Resume, Chat, Contact, RAG, Telegram and existing case studies unchanged |

## 6. Quality and recovery policy

- Always branch from latest clean `main`. Never commit directly to `main`.
- One migration concern per PR, squash merge only after all required CI jobs pass.
- Do not force-push or reset branches without reviewing local status.
- Before any SQLite path change, hash/backup both the seed and disposable runtime test database. Production filesystem is ephemeral; do not assume stable data or perform destructive production operations.
- Keep a pre-migration file map and old Git ref to support rollback via reverting the PR.
- Check frontend and backend runtime behavior, not only `tsc` and `pytest`.
- Cross-platform CI includes Windows PowerShell local checks and Linux GitHub jobs. Repo hygiene rejects raw Cyrillic in non-`.ru` documents, so this `SESSION_NOTES.md` is intentionally in English.
- Do not migrate, publish, or add live-mail destinations without explicit approval. Existing mail allowlist and auth safeguards must be preserved.

## 7. First-commit procedure (for user)

1. Open new chat title: `Portfolio Architecture — Foundation & Fleet Hub Migration`.
2. In PowerShell, from clean repository root: `git switch main; git pull --ff-only origin main; git switch -c refactor/portfolio-foundation`.
3. Extract the provided ZIP under the repository root. Run `python install_portfolio_foundation.py` (dry run) and `python install_portfolio_foundation.py --apply` to patch Taskfile safely.
4. Remove the one-time `install_portfolio_foundation.py` and `README_INSTALL.txt` before staging. `portfolio/` files, `SESSION_NOTES.md`, `scripts/check-portfolio-foundation.mjs`, `docs/architecture/portfolio.md` and modified `Taskfile.yml` are the deliverable.
5. Run: `node scripts/check-portfolio-foundation.mjs`, `task portfolio:check`, `task repo:check`, `task ci`.
6. Stage only approved files, `git diff --cached --check`, confirm no SQLite/code movements, commit, push branch, open PR to main.
7. After PR 1 merge, continue with PR 2 in a fresh branch. If any CI error occurs, fix only the exact failure, rerun checks and avoid unrelated refactors.

## 8. Notes for the next conversation / agent

- User wants a **single-folder-per-demo architecture** in the site repository, not separate repos/sites. Prior proposals of separate deployments or independently deployed services are out of scope.
- `portfolio/fleet_hub/` is the canonical destination; `frontend/`/`backend/` are host infrastructure only.
- First PR is **docs, hidden metadata and structural check only**. No moving Fleet code yet.
- The user wants downloadable files and precise Windows PowerShell commands.
- Check current GitHub `main` before beginning subsequent PRs; treat this inventory as dated.
- User's already-approved demo seed contains mock data and should not be anonymised or edited during architecture migration.
- The project intentionally uses Vercel plus Render Free; do not suggest a paid disk or changed storage mode as a prerequisite to architectural refactoring.
