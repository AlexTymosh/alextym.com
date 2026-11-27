# ADR 0002 — Freeze legacy Preferans at PR42

- Date: 2026-11-27
- Status: Candidate baseline, subject to Owner applying the pinned package.
- Context: The Owner prohibits modification of original Preferans. Latest verified main at SP01 preparation is `1e76eaa4c0ba58ceed0e5b5615917a6ee229f777`, after PR42. No later legacy changes may be silently included.
- Alternatives: maintain only a Git tag (insufficient enforcement), share mutable engine package with legacy (rejected), snapshot plus verified inventory and independent future engine (selected).
- Decision: generate the manifest from the exact baseline Git tree on application. Protect paths containing `preferans` outside SamePlace; compare tree/index/working tree and include negative tests. Fetch the immutable baseline for shallow CI; reject absent or altered baseline. Keep all old API/route/grant/data/behavior unchanged. No runtime legacy import. Future new Preferans engine lives in SamePlace and is copied from pinned source with provenance and differential tests.
- Consequences: changes to legacy or freeze guard need explicit exceptional Owner review. Guard itself is not tamper-proof against a reviewer approving modified CI. Pin the reference and protect guard/manifest/workflow through existing branch protection and review policy (no repository settings modified). If a legacy security issue appears, escalate separately, not as an unrelated fix.
- Validation: synthetic Git cases, actual inventory check on apply, existing regression suite, freeze gate in project CI.
- Supersedes: provisional PR41 planning baseline.
