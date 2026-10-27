# Fleet VOR Hub — embedded portfolio demo

Fleet VOR Hub is the first portfolio application to be colocated under `portfolio/fleet_hub/`.

## Current state

**Foundation stage (PR 1):** this folder holds only metadata, architecture documentation and planned ownership directories. The runnable implementation is still located in:

- `frontend/app/fleet-vor-hub/` (Next.js routes and all UI)
- `backend/app/api/vor*.py` (eight API router modules)
- `backend/app/services/vor*.py` (services and SQLite seed)
- `backend/tests/test_vor*.py` and related test modules

Do not duplicate or move source code in the foundation PR. Future PRs move the frontend first, then backend and SQLite, keeping the public contract intact.

## Stable URLs

- Demo: `/fleet-vor-hub`
- API: `/api/vor/*`
- Historical redirects: `/fleet-vor-hub/register`, `/fleet-vor-hub/new-defect`, `/fleet-vor-hub/process` (currently redirect to `/fleet-vor-hub`).

## Data contract

Approved demo seed SHA-256:

`db67e2a8e121f38efddd54215edae0e28c855524920fdefab78d2d656b466532`

Approved snapshot contains 20 vehicles, 42 tickets and 219 events; `GX24 KLM` is assigned to `Basingstoke` / `Jason W.`. Keep the SQLite bytes unchanged during architectural moves. The existing `backend/tests/test_vor_seed_contract.py` enforces the seed contract.

## No independent deployment

Fleet Hub is for demonstration inside `alextym.com`, not a standalone SaaS product. It will share the site's Next.js and FastAPI processes, with clear module boundaries and an independent demo SQLite file.

See `docs/migration-map.md` for the inventory of current files and follow-up steps.
