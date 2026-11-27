# Backend

Editable package `alextym-sameplace`; namespace `sameplace`. Public entry: `sameplace.router.router`. The host injects the fail-closed Lab/project guard. The only route in SP01 is a read-only status endpoint; it performs no database or external calls itself. `contracts/` contains validated metadata only. No Firestore repositories, scheduler, rooms, WebSocket or actual module installation exists yet. Maintain inward dependencies (pure contracts/domain must not import host or transport).
