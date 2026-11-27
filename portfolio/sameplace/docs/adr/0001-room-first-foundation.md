# ADR 0001 — Room-first embedded foundation

- Date: 2026-11-27
- Status: Accepted product direction; implementation candidate SP01
- Context: Permanent social rooms require independent game lifecycle; existing Preferans is a working portfolio project that must remain unchanged. Budget is GBP 0.
- Alternatives: Extend legacy (rejected: violates freeze and entangles the room with one game); deploy new independent services (deferred: unnecessary cost and operations); embed independent module (selected).
- Decision: register an isolated SamePlace Python package and frontend public entrypoint, guard both route/API with server feature flags and current Lab grant, hide from public catalog, no data/media provider at foundation. Reuse shared authentication through host composition only. Room-scoped invitation authorization will be designed in SP02, without granting access to other projects. Maintain separate module and state schema versions. All technical docs English except canonical Russian specification; locale scoped to project.
- Consequences: small additive host changes needed for packaging, routing, CI. Shared quotas remain a release risk. Activity lifecycle waits for Room Core; no premature plugin loading.
- Validation: host boundary checks, mocked authorization, manifest/locale tests and full CI; actual production release gated separately.
- Supersedes: none.
