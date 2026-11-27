# SamePlace

Private, persistent meeting rooms and independently versioned activities. SP01 is a disabled foundation, not a playable product.

- [Canonical Russian requirements](docs/SAMEPLACE_FULL_TECHNICAL_SPECIFICATION.ru.md)
- [Session ledger](SESSION_NOTES.md) and [development plan](docs/DEVELOPMENT_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md), [localization](docs/LOCALIZATION.md), [test strategy](docs/TEST_STRATEGY.md)

The project is embedded in the existing Next.js and FastAPI hosts. Domain logic belongs here; the hosts only compose entrypoints and enforce host identity. `SAMEPLACE_ENABLED` must remain unset or false in production until release approval. Both the page and the API also require Portfolio Lab to be enabled and a valid project grant (SP01 only). Room-scoped invitation admission is SP02; there is no guest bypass in SP01.

All engineering documentation, identifiers, comments, commit messages and ADRs are English. The canonical requirements are Russian (`.ru.md`) and initial user-facing text is Russian in localized resources. No global site localization. No paid infrastructure or data migration. Legacy Preferans remains frozen at the baseline recorded in `docs/legacy-freeze.json`.

Run the repository CI and the project-specific checks in [test strategy](docs/TEST_STRATEGY.md). No separate npm install inside this project.
