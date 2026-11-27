# ADR 0003 — Scoped room identity and durable aggregate transactions

Status: proposed for SP02 acceptance, 2026-11-27.

Context: SP01's global project grant would reject a legitimate invited user. Granting Test/Admin automatically or weakening shared Lab admission would expand access. Room and game/meeting lifetimes must differ, and the free Firestore budget must not incur idle polling.

Decision: separate scoped credential adapter and room membership authorization; retain the SP01 status guard and all global admission rules. Existing Lab record denials are respected. New verified Firebase account can prove identity without global grant; invitation grants only one room. Scoped BFF cookie, exact allowlist and origin check. A new collection with versioned room aggregate, immutable slug, UID index/counters, audit and idempotency records; transaction writes buffered after all reads. Owner-controlled storage cap and configured capacity, future active lease enforcement. Generate invitation links with URL fragment to avoid HTTP path logs; keep original path compatibility but do not distribute it. Do not include personal names in artifacts.

Alternatives rejected: modifying shared admission, creating another Firebase project/account database, optimistic client writes, scanning global rooms, per-game room identity, storing plaintext invitation tokens, paid TTL, background polling. Consequences: a bounded aggregate and small per-user list are sufficient for initial private rooms; high-scale storage, cleanup, privacy deletion, realtime and multi-instance behavior remain separately gated. The explicit local logout semantics and fragment URL need Owner review; neither changes other portfolio apps. No production activation or paid services.
