# Portfolio architecture — host and project boundaries

**Status:** target architecture defined; migration not yet performed.

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

## Implementation phases

See `SESSION_NOTES.md` for detailed PR slices, checklists and recovery instructions. First PR establishes metadata and structural validation only; no code relocation, package workspace, Docker or Vercel changes.
