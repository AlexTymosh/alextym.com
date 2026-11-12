# Portfolio architecture — host and project boundaries

**Status (2026-11-04):** PR #223 (`refactor(fleet-db): isolate SQLite lifecycle
and migrations`) has been squash-merged into `main` at `c020c813d452`.
Fleet API auth and email delivery isolation are now under review on the
unmerged branch `refactor/fleet-api-delivery-boundaries`. The deployment
remains one Next.js host on Vercel and one FastAPI host on Render.

## Target

`alextym.com` is a single monorepo with one Next.js host (Vercel) and one FastAPI host (Render). Each embedded demonstration application owns its implementation under `portfolio/<project_id>/`. These projects will never need standalone repositories, websites or dedicated services.

```text
frontend/app/<public-route>/page.tsx --> portfolio/<id>/frontend (public entry)
backend/app/main.py                 --> portfolio/<id>/backend  (public router)
portfolio/<id>/                    -X-> frontend website internals
portfolio/<id>/                    -X-> backend website internals
portfolio/<id>/                    -X-> another project's internals
```

Host adapters should be *thin*: routing, deployment configuration and explicitly provided external capabilities only; no fleet domain logic.

## Planned Portfolio Lab identity and authorization

**Status:** Requirements agreed; identity and access implementation is pending.
The following is an intended architecture, not a claim about production.

- [Portfolio Lab identity/access specification](../specifications/portfolio-lab-auth-access.md)
- [ADR-0001: Identity and access boundaries](../adr/0001-portfolio-lab-identity-access.md)
- [Six-PR implementation plan](../../SESSION_NOTES.md)

The website host will own the shared Firebase identity and Firestore authorization
control plane. The Git project registry and project manifests remain the canonical
catalogue. Each protected FastAPI request, including calls to the direct Render
origin, must independently enforce current identity, project role and capability.
Front-end route visibility alone is not sufficient. Session transport between
Vercel and Render must be proven in PR 2 before implementation proceeds.

Each registered demonstration remains responsible for its domain logic, UI,
API and business persistence. Fleet keeps its current SQLite lifecycle and routes
until its separate authentication migration in PR 5. `View` is read-only;
`Test`/`Admin` may initiate real actions within Owner-configured quotas.
New projects receive no automatic non-Owner grants. Legacy password login must
not be accepted in parallel with the new authorization after cutover.

This is logical domain and data isolation, not separate process/CPU isolation.
The current Fleet-specific regression checks remain in place alongside new
generic project-boundary checks.

## Ownership

| Layer | Owned by | Allowed responsibility |
| --- | --- | --- |
| `/`, Resume, Chat, Contact, global navigation | Website | Personal portfolio, chat and generic site identity |
| `/fleet-vor-hub` route adapter | Website | Import/render Fleet public frontend entry |
| `/api/vor/*` router adapter | Website | Register Fleet public router (no ticket logic) |
| Fleet UI, CSS, local images | Fleet | Fleet application implementation |
| Fleet API and domain services | Fleet | Business rules, auth/session for the demo, operations |
| Fleet SQLite and migrations | Fleet | Independent demo data and its integrity contract |
| `portfolio/catalog/` | Portfolio metadata | Stable metadata, not imported runtime implementation |
| `Taskfile.yml`, CI, Docker, Vercel/Render config | Host | Build/test wiring and deployment |

No generic shared package or plugin discovery framework is required yet. If an actually reusable primitive appears, create a small neutral `shared/` module with an explicit contract; never move domain logic there.

## Boundaries to verify before and after code migration

1. Imports: no project imports of website business modules or cross-project internals; host code imports only project public entries. Build a static import-boundary test when modules are moved. Foundation metadata alone cannot yet enforce this rule.
2. CSS: Fleet global selectors must not target unrelated website pages. Site global styles must not override Fleet's internal controls unexpectedly. Compare screenshots before/after.
3. Layout: retain existing URLs; evaluate Next.js route groups separately, without redesigning Chat/Resume/Contact.
4. Contracts: record the FastAPI router path/method set, cookie paths and status codes before moving backend modules; run golden-path smoke tests afterward.
5. Data: approved seed has immutable SHA-256 `db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`; use SQLite integrity/foreign-key checks and test read/write behavior against disposable runtime copies. Never change the user's working DB as part of file moves.
6. Build: Vercel must include `portfolio/` source outside `frontend/`; Docker must copy/install the backend project package. Keep existing deploy services.
7. Tests: no removal of security, exports, import, reconciliation, or workflow coverage. After relocation, tests must run in GitHub CI, not only locally.
8. Portfolio publication: `project.json` and registry do not publish a catalogue. Keep `catalog.visible=false` and no `/portfolio` route/menu item until separately approved.

## Invariants for every PR

- `task ci` passes locally and GitHub CI jobs pass (project/backend/frontend/RAG/docker).
- `/fleet-vor-hub`, redirects and `/api/vor/*` remain compatible.
- `/fleet-vor-hub-01` and `/api/vor-01` remain retired.
- No change to the Fleet SQLite seed bytes, accepted data model or existing live environment settings.
- No behavior change in Resume, Chat, Contact, RAG, Telegram or unrelated case studies.
- No new paid infrastructure.

## Current lifecycle and rollout status

Fleet backend implementation lives in the installable
`portfolio/fleet_hub/backend/src/fleet_hub/` package. The host imports only
`fleet_hub.router` and the public startup hook
`fleet_hub.bootstrap.prepare_demo_database`. The frontend host uses the Fleet
public `@fleet-hub` entry; feature-local UI code remains under
`portfolio/fleet_hub/frontend/src/`.

The merged SQLite persistence refactor (PR #223) added:

- `persistence/sqlite.py` for configured SQLite connections and closure.
- `persistence/migrations.py` for versioned v1 migration implementations.
- `persistence/schema.py` for per-DB schema readiness and interprocess locking.
- Atomic seed publication, read-only ready-schema probes, and recovery paths.
- Optional startup bootstrap in the FastAPI lifespan, with lazy fallback for
  standalone Fleet tests and integrations.
- Fault-injection, concurrent-open, and data-preservation tests on disposable
  SQLite files.

Ready databases avoid repeating v1 schema initialization or v2/operations DDL.
Incomplete schemas retain guarded, idempotent recovery. The v1 migration
rollback guard protects pending writes for each version, but the full upgrade
is **not one atomic transaction**: existing successful commit boundaries remain.

**Next PR (not yet opened/merged):** Fleet API dependency and delivery boundaries
in `refactor/fleet-api-delivery-boundaries`: `fleet_hub.api.dependencies` owns
the session and Origin checks; `fleet_hub.services.message_delivery` owns
recipient policy, quota and Resend orchestration. Keyed live email attempts
use an additive SQLite journal and provider `Idempotency-Key`; existing
unkeyed callers retain the legacy behavior. Accepted provider delivery
and the subsequent local event write are not one atomic transaction.
Unknown outcomes are held for manual reconciliation, not resent with
the same request ID. Full PR CI and post-merge smoke are still pending.
See `SESSION_NOTES.md` for the current checkpoint.

## Historical implementation — frontend and source relocation

## Implementation status — PR 4 (frontend isolation audit)

The website retains its root layout, navigation, footer and shared browser-level resets. Fleet UI and assets live under `portfolio/fleet_hub/frontend/src/` with locally scoped CSS Modules. `scripts/check-website-portfolio-boundaries.mjs` rejects project-side global CSS, cross-boundary imports, direct website imports of Fleet internals, route changes and accidental publication of a portfolio menu. See `portfolio/fleet_hub/docs/css-boundary-audit.md` for evidence, limitations and acceptance criteria.

Route groups were reviewed and deferred because they would change layout lifecycle without a verified need. Full browser-level isolation is not claimed: the single Next.js host necessarily shares document-wide CSS baseline and metadata. Existing Playwright regression tests guard the user-visible contract.

## PR 5 — final source and tooling handoff

Retire only obsolete, one-time Fleet migration installers and checks; preserve local launchers and SQLite backup tooling. New `scripts/check-fleet-legacy-tooling.mjs` rejects stale scripts in CI. See `portfolio/fleet_hub/docs/legacy-tooling-audit.md`.

New browser tests cover mocked authenticated Fleet navigation and sign-out; existing Python tests cover real backend authentication and disposable SQLite. Real Vercel/Render deployment validation is a separate post-merge manual gate: `portfolio/fleet_hub/docs/deployment-smoke.md`.

## Tooling cleanup correction (2026-11-09)

The PR 5 tool-retention paragraph above is historical. The one-time legacy
migration audit is retired from CI; `task portfolio:check` retains the generic
portfolio registry guard and all website/Fleet ownership boundaries. The
pre-migration online SQLite backup helper and local Fleet launchers remain
available for ongoing data safety and development.
