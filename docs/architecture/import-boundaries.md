# Python architecture import boundaries (Step 07)

This guard prevents new import-direction regressions in the website backend and
embedded Fleet Hub. It is a focused architectural constraint, not a general
static-analysis or security tool.

## Rules

| Owning modules | Forbidden imports |
| --- | --- |
| `app.domain.*` | `app.*` outside `app.domain` |
| `app.repositories.*` | `app.services.*`, `app.api.*` |
| `fleet_hub.services.*` | `fleet_hub.api.*`, `app.api.*` |
| `fleet_hub.api.*` | Sibling Fleet API routers (except shared `dependencies`) |

The public Fleet router composer `fleet_hub.router` is **not** part of the
`sibling API routers` rule: it is intentionally responsible for wiring routers.

The historical edge `fleet_hub.api.vor → fleet_hub.api.vor_checklist`
was removed in Step 10D. Both routers now call a neutral Fleet service for
checklist-gated stage advancement; shared HTTP dependencies remain in
`fleet_hub.api.dependencies`. There are no remaining grandfathered sibling
router import exceptions. Future cross-router dependencies must be rejected.


## Execution

Run `task backend:imports` (or from `backend/`,
`uv run python -m scripts.check_import_boundaries`). The task is part of
`backend:check` and therefore runs in local `task ci` and GitHub's `backend`
job without changing the workflow file. Tests use in-memory source fixtures
written to `tmp_path`: `backend/tests/test_import_boundaries.py`.

The checker reads only Python source within the four directories above. It
supports absolute and relative `import`/`from` forms and literal module names
in direct `importlib.import_module(...)`/`__import__(...)` calls. Computed
imports, runtime monkeypatching, and arbitrary reflection are **not** covered.
Violations report the file path and source line. The checker fails closed on
missing package roots or invalid Python syntax.

No checks in this guard or its tests read `SESSION_NOTES.md`; that file remains
human-maintained documentation rather than a CI gate.
