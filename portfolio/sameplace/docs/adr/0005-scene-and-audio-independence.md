# ADR 0005 — Scene and music independence

Status: accepted for SP04 candidate, release evidence pending.

Context: The room persists independently of activities, scenes and media. Existing Room Core and Social/Realtime transactions and permission boundaries must remain intact. The legacy application is frozen; the project has no paid media budget.

Decision: use an independent bounded `decor_<room-id>` document in the existing SamePlace collection, with per-location scene revisions and per-scope music revisions. Persist only validated published scenes and changes. Use private per-UID template libraries. Reuse the existing authorized-room and command receipt ports, shared quota circuit and write limiter. Use post-commit room hub fencing and current room revision as invalidation; no additional heartbeat writes. Render from a trusted SVG catalogue; use a stable client audio component, source-state clock, local permission and independent local volume/mute. Media is fetched directly by each browser, never proxied by FastAPI. Radio is unavailable by default; original test WAV sources are available. No global CSS or website ownership changes.

Alternatives rejected: coupling audio to a skin component or game; persisting every drag event; arbitrary image/HTML/URL imports; direct browser Firestore; adding a separate service or paid stream relay. Consequences: room revision notifications can refresh core metadata as well as decor; real usage must be measured. This does not provide sample-accurate radio synchronization or validated commercial artwork. Future Activity Host must enforce safe boundaries for active games. Provider rights, actual device tests and Emulator acceptance remain release gates.
