# SamePlace

Private, persistent meeting rooms and independently versioned activities. SP02 adds private persistent room management on top of the disabled foundation; not a playable product.

- [Canonical Russian requirements](docs/SAMEPLACE_FULL_TECHNICAL_SPECIFICATION.ru.md)
- [Session ledger](SESSION_NOTES.md) and [development plan](docs/DEVELOPMENT_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md), [localization](docs/LOCALIZATION.md), [test strategy](docs/TEST_STRATEGY.md)

The project is embedded in the existing Next.js and FastAPI hosts. Domain logic belongs here; the hosts only compose entrypoints and enforce host identity. `SAMEPLACE_ENABLED` must remain unset or false in production until release approval. Both entrypoints require Portfolio Lab to be enabled. The status endpoint retains its original project grant, while Room Core uses separately verified identity and scoped memberships. See [security](docs/SECURITY_AND_PERMISSIONS.md), [domain model](docs/DOMAIN_MODEL.md) and [HTTP contract](docs/API_CONTRACT.md).

All engineering documentation, identifiers, comments, commit messages and ADRs are English. The canonical requirements are Russian (`.ru.md`) and initial user-facing text is Russian in localized resources. No global site localization. No paid infrastructure or data migration. Legacy Preferans remains frozen at the baseline recorded in `docs/legacy-freeze.json`.

Run the repository CI and the project-specific checks in [test strategy](docs/TEST_STRATEGY.md). No separate npm install inside this project.


## SP03 room shell and social/realtime

Private room members may meet even without the owner. Profile, friendships, room favourites, recent visits, chat and internal waiting-at-room notices are scoped to SamePlace. The one-worker realtime feature is disabled by default. See [realtime protocol](docs/REALTIME_AND_MEDIA.md), [resource budget](docs/RESOURCE_BUDGET.md), [ADR 0004](docs/adr/0004-single-worker-realtime.md) and [session ledger](SESSION_NOTES.md). All release gates, local CI and local Emulator/real-device verification still apply. No automatic email or SMS, music, video, or game engine in this stage.

## SP04: scenes and music

The private room includes original schematic scene presets, per-location designer editor, private reusable interior templates and a persistent audio controller. Source catalogue starts with two original test tones; external radio is operator-disabled until rights review. See [Interior engine](docs/INTERIOR_ENGINE.md), [asset register](docs/ASSET_LICENSES.md), [media operations](docs/REALTIME_AND_MEDIA.md) and [session ledger](SESSION_NOTES.md). Production stays disabled.

## SP05 room voice/video and testing

SP01–SP04 merged. SP05 is the room media candidate; Activity SDK moves to SP06 and Preferans to SP07 (ADR 0006). Room management, presence, chat and decor are testable in a configured isolated environment. After SP05 CI, use [MEDIA_OPERATIONS](docs/MEDIA_OPERATIONS.md) for a private two-user walkthrough, feature flags, no-cost constraints, real-device acceptance and rollback. Canonical room list path `/portfolio/sameplace/rooms`; hosted production remains disabled until explicitly authorized. No public game is available yet.
