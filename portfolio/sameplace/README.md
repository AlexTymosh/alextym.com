# SamePlace

Private, persistent meeting rooms and independently versioned activities. SP02 adds private persistent room management on top of the disabled foundation; not a playable product.

- [Canonical Russian requirements](docs/SAMEPLACE_FULL_TECHNICAL_SPECIFICATION.ru.md)
- [Session ledger](SESSION_NOTES.md) and [development plan](docs/DEVELOPMENT_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md), [localization](docs/LOCALIZATION.md), [test strategy](docs/TEST_STRATEGY.md)

The project is embedded in the existing Next.js and FastAPI hosts. Domain logic belongs here; the hosts only compose entrypoints and enforce host identity. `SAMEPLACE_ENABLED` must remain unset or false in production until release approval. Both entrypoints require Portfolio Lab to be enabled. The status endpoint retains its original project grant, while Room Core uses separately verified identity and scoped memberships. See [security](docs/SECURITY_AND_PERMISSIONS.md), [domain model](docs/DOMAIN_MODEL.md) and [HTTP contract](docs/API_CONTRACT.md).

All engineering documentation, identifiers, comments, commit messages and ADRs are English. The canonical requirements are Russian (`.ru.md`) and initial user-facing text is Russian in localized resources. No global site localization. No paid infrastructure or data migration. Legacy Preferans remains frozen at the baseline recorded in `docs/legacy-freeze.json`.

Run the repository CI and the project-specific checks in [test strategy](docs/TEST_STRATEGY.md). No separate npm install inside this project.
