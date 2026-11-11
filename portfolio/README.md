# Portfolio project modules

This directory is the **canonical home** for demonstration-only applications embedded in `alextym.com`.

**Status:** active. Fleet VOR Hub lives in `portfolio/fleet_hub/` and is mounted through the existing Next.js and FastAPI hosts. Other registered modules follow the same isolation contract.

## Directory contract

- `catalog/registry.json` lists project IDs for build-time metadata validation. It does not publish routes or menu entries.
- `<project_id>/project.json` describes the application's public metadata and current routes.
- `<project_id>/frontend/` will own its UI, components and project-local CSS.
- `<project_id>/backend/` will own project APIs, services and demo persistence.
- `<project_id>/tests/` will own application-specific tests.
- `<project_id>/docs/` will own architectural and demo documentation.
- Shared website infrastructure (`frontend/` and `backend/`) remains the host, not a destination for project business logic.

A future project should follow `portfolio/fleet_hub/` as a structural pattern. Do **not** copy its vehicle and workflow domain logic.

## Dependencies

```text
website Next.js route   --> project frontend public entry
website FastAPI startup --> project backend public router
project internal code   -X-> website implementation
project A internals     -X-> project B internals
```

The project may depend on neutral platform-level libraries if they are explicitly documented. It must never directly import website Chat, Resume, Contact or another portfolio application's internals.

No independent site, repository, deployment or database service is planned for portfolio projects. The host website will continue to run in the existing Vercel + Render infrastructure.

## Publication

A `project.json` or registry entry **does not automatically publish** a project. Publication and site navigation are separate product decisions. The existing Fleet Hub demo remains at `/fleet-vor-hub`.

## Validate

From the repository root:

```bash
node scripts/check-portfolio-registry.mjs
task repo:check
```

See `docs/architecture/portfolio.md` and the architecture release audit for the current module boundaries. Historical migration decisions are in Git history.
